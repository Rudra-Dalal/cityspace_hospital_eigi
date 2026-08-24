"""Shared patient appointment application service for booking, listing, and cancelling appointments."""

from datetime import date as date_cls
from typing import Any, Dict, List, Optional
from pymongo.errors import DuplicateKeyError

from app.core.config import VALID_SLOTS, get_settings
from app.cruds import appointment_crud, hospital_crud, user_crud
from app.models.appointment_model import (
    AppointmentStatus,
    appointment_document,
    serialize_appointment,
)
from app.services.patient_discovery_service import validate_booking_date
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_AVAILABLE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


class BookingError(Exception):
    """Domain exception for booking rule violations."""
    pass


class SlotConflictError(BookingError):
    """Domain exception when slot is already booked."""
    pass


async def book_patient_appointment(
    patient: Dict[str, Any],
    date_str: str,
    slot: str,
    reason: str,
    hospital_id: Optional[str] = None,
    doctor_id: Optional[str] = None,
    temperature: Optional[float] = None,
    symptoms: Optional[List[str]] = None,
    tz_name: str = "Asia/Kolkata",
) -> Dict[str, Any]:
    """
    Validate and book an appointment with multi-tenant and clinical checks.
    Throws BookingError or SlotConflictError on business rule violations.
    """
    if patient.get("role") not in ("customer", "patient"):
        raise BookingError("Only patients/customers can book appointments.")
    if patient.get("is_active") is False:
        raise BookingError("Account is inactive.")

    if not reason or not reason.strip():
        raise BookingError("Reason for appointment is required.")

    # 1. Validate date within booking window
    try:
        target_date = validate_booking_date(date_str, tz_name=tz_name)
    except ValueError as exc:
        raise BookingError(str(exc)) from exc

    day_of_week = target_date.strftime("%A")

    # 2. Validate hospital & doctor
    if hospital_id and doctor_id:
        hospital = await hospital_crud.get_hospital_by_id(hospital_id)
        if not hospital or hospital.get("status") != "active":
            raise BookingError("Selected hospital is invalid or inactive.")

        doctor = await user_crud.get_user_by_id(doctor_id)
        if not doctor or doctor.get("role") != "doctor" or doctor.get("is_active") is False:
            raise BookingError("Selected doctor is invalid or inactive.")

        # Doctor must belong to the chosen hospital (if assigned)
        doc_hid = doctor.get("hospital_id")
        if doc_hid and doc_hid != hospital_id:
            raise BookingError("Doctor is not assigned to the selected hospital.")

        # Weekday availability check
        available_days = doctor.get("available_days") or DEFAULT_AVAILABLE_DAYS
        if day_of_week not in available_days:
            raise BookingError(f"Doctor is not available on {day_of_week}s.")

        # Valid slots check
        valid_slots = doctor.get("valid_slots") or list(VALID_SLOTS)
        if slot not in valid_slots:
            raise BookingError(f"Invalid slot for this doctor. Available slots: {', '.join(valid_slots[:6])}...")
    elif hospital_id or doctor_id:
        raise BookingError("Both hospital_id and doctor_id must be provided together.")
    else:
        # Backward compatibility fallback when omitted
        doctor = await user_crud.get_user_by_email(get_settings().doctor_email)
        if not doctor:
            raise BookingError("Default doctor account not found.")
        doctor_id = str(doctor["_id"])
        hospital_id = doctor.get("hospital_id")

        available_days = doctor.get("available_days") or DEFAULT_AVAILABLE_DAYS
        if day_of_week not in available_days:
            raise BookingError(f"Doctor is not available on {day_of_week}s.")
        valid_slots = doctor.get("valid_slots") or list(VALID_SLOTS)
        if slot not in valid_slots:
            raise BookingError("Invalid appointment time slot.")

    # 3. Create document and insert atomically
    patient_id = str(patient["_id"])
    doc = appointment_document(
        patient_id=patient_id,
        date=date_str,
        slot=slot,
        reason=reason.strip(),
        temperature=temperature,
        symptoms=symptoms or [],
        hospital_id=hospital_id,
        doctor_id=doctor_id,
    )

    try:
        created = await appointment_crud.create_appointment(doc)
    except DuplicateKeyError:
        raise SlotConflictError(
            f"Slot {slot} on {date_str} is already booked for this doctor. Please choose another slot."
        )

    # 4. Resolve metadata for response
    doctor_obj = await user_crud.get_user_by_id(doctor_id) if doctor_id else None
    hospital_obj = await hospital_crud.get_hospital_by_id(hospital_id) if hospital_id else None

    doctor_name = f"Dr. {doctor_obj.get('first_name', '')} {doctor_obj.get('last_name', '')}".strip() if doctor_obj else None
    hospital_name = hospital_obj.get("name") if hospital_obj else None
    hospital_city = hospital_obj.get("city") if hospital_obj else None

    res = serialize_appointment(created)
    res["doctor_name"] = doctor_name
    res["hospital_name"] = hospital_name
    res["hospital_city"] = hospital_city
    return res


async def get_patient_appointments(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieve all appointments for a patient with resolved hospital and doctor names."""
    docs = await appointment_crud.get_patient_appointments(patient_id)
    results: List[Dict[str, Any]] = []
    for doc in docs:
        d_id = doc.get("doctor_id")
        h_id = doc.get("hospital_id")
        doctor = await user_crud.get_user_by_id(d_id) if d_id else None
        hospital = await hospital_crud.get_hospital_by_id(h_id) if h_id else None

        d_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip() if doctor else None
        h_name = hospital.get("name") if hospital else None
        h_city = hospital.get("city") if hospital else None

        item = serialize_appointment(doc)
        item["doctor_name"] = d_name
        item["hospital_name"] = h_name
        item["hospital_city"] = h_city
        results.append(item)
    return results



async def cancel_patient_appointment(appointment_id: str, patient_id: str) -> Dict[str, Any]:
    """Cancel an appointment owned by the patient."""
    appt = await appointment_crud.get_appointment_by_id(appointment_id)
    if not appt:
        raise BookingError("Appointment not found.")
    if appt.get("patient_id") != patient_id:
        raise BookingError("You do not have permission to cancel this appointment.")
    if appt.get("status") == AppointmentStatus.CANCELLED.value:
        raise BookingError("Appointment is already cancelled.")

    updated = await appointment_crud.update_appointment_status(
        appointment_id,
        AppointmentStatus.CANCELLED.value,
    )
    if not updated:
        raise BookingError("Failed to cancel appointment.")

    return {
        "id": appointment_id,
        "status": AppointmentStatus.CANCELLED.value,
        "message": "Appointment cancelled successfully. The slot is now available.",
    }
