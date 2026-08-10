"""Appointment business logic — booking gates, free slots, cancel."""

from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import VALID_SLOTS, get_settings
from app.cruds import appointment_crud
from app.models.appointment_model import (
    AppointmentStatus,
    appointment_document,
    serialize_appointment,
)
from app.schemas.appointment_schema import AcceptResponse, AppointmentCreate, AppointmentOut, CancelResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


def validate_booking_date(date_str: str) -> date_cls:
    """Gate 3 — date must be today or up to booking_window_days ahead, never past."""
    settings = get_settings()
    try:
        target = date_cls.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date must be a valid ISO date YYYY-MM-DD",
        ) from exc

    today = datetime.now(timezone.utc).date()
    max_date = today.fromordinal(today.toordinal() + settings.booking_window_days)

    if target < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book an appointment in the past.",
        )
    if target > max_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointments can only be booked up to {settings.booking_window_days} days ahead.",
        )
    return target


async def get_free_slots(date_str: str, doctor_id: Optional[str] = None, hospital_id: Optional[str] = None) -> Dict[str, Any]:
    validate_booking_date(date_str)
    booked = set(await appointment_crud.get_booked_slots_for_date(
        date_str,
        doctor_id=doctor_id,
        hospital_id=hospital_id,
    ))
    free = [s for s in VALID_SLOTS if s not in booked]
    return {"date": date_str, "free_slots": free}


async def book_appointment(
    payload: AppointmentCreate,
    current_user: Dict[str, Any],
) -> AppointmentOut:
    """
    Gates 2–4 (Gate 1 already handled by auth dependency).
    Identity comes only from the JWT — never from the request body.
    """
    # Accept both "customer" and legacy "patient"
    if current_user.get("role") not in ("customer", "patient"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can book appointments.",
        )

    validate_booking_date(payload.date)

    if payload.slot not in VALID_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid slot. Choose one of: {', '.join(VALID_SLOTS)}",
        )

    # Resolve hospital and doctor for this booking
    from app.cruds import hospital_crud
    from app.core.database import get_database

    hospital_id: Optional[str] = payload.hospital_id
    doctor_id: Optional[str] = payload.doctor_id

    # Fall back to the first active hospital/doctor if not provided (backward-compat)
    if not hospital_id:
        hospitals = await hospital_crud.get_all_hospitals(status="active")
        if not hospitals:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active hospital found.",
            )
        hospital_id = str(hospitals[0]["_id"])

    if not doctor_id:
        db = get_database()
        doctor = await db.users.find_one({"hospital_id": hospital_id, "role": "doctor"})
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No doctor found for this hospital.",
            )
        doctor_id = str(doctor["_id"])

    # Polite pre-check (helpful early answer)
    if await appointment_crud.slot_is_booked(payload.date, payload.slot, doctor_id=doctor_id, hospital_id=hospital_id):
        logger.info(
            "Booking conflict (pre-check): date=%s slot=%s user=%s",
            payload.date,
            payload.slot,
            current_user.get("email"),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is already booked. Please choose another.",
        )

    doc = appointment_document(
        patient_id=str(current_user["_id"]),
        hospital_id=hospital_id,
        doctor_id=doctor_id,
        date=payload.date,
        slot=payload.slot,
        reason=payload.reason,
        temperature=payload.temperature,
        symptoms=payload.symptoms,
    )

    try:
        created = await appointment_crud.create_appointment(doc)
    except DuplicateKeyError:
        # Steel door — race-condition guard via partial unique index
        logger.warning(
            "Booking conflict (duplicate key): date=%s slot=%s user=%s",
            payload.date,
            payload.slot,
            current_user.get("email"),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is already booked. Please choose another.",
        )
    except Exception:
        logger.exception("Unexpected error while booking appointment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while booking.",
        )

    logger.info(
        "Appointment booked: id=%s date=%s slot=%s patient=%s hospital=%s doctor=%s",
        created["_id"],
        created["date"],
        created["slot"],
        current_user.get("email"),
        hospital_id,
        doctor_id,
    )
    return AppointmentOut(**serialize_appointment(created))


async def list_my_appointments(current_user: Dict[str, Any]) -> List[AppointmentOut]:
    appointments = await appointment_crud.get_appointments_for_patient(
        str(current_user["_id"])
    )
    return [AppointmentOut(**serialize_appointment(a)) for a in appointments]


async def cancel_my_appointment(
    appointment_id: str,
    current_user: Dict[str, Any],
) -> CancelResponse:
    appt = await appointment_crud.get_appointment_by_id(appointment_id)
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    # Ownership check — customers cancel only their own; doctors/managers may cancel any in their hospital
    is_owner = appt["patient_id"] == str(current_user["_id"])
    user_role = current_user.get("role", "")
    is_privileged = user_role in ("doctor", "hospital_manager", "super_admin")

    if not is_owner and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to cancel this appointment.",
        )

    # Hospital scoping for managers/doctors
    if is_privileged and user_role != "super_admin":
        if appt.get("hospital_id") != current_user.get("hospital_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This appointment belongs to a different hospital.",
            )

    if appt["status"] == AppointmentStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This appointment is already cancelled.",
        )

    updated = await appointment_crud.cancel_appointment(appointment_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to cancel this appointment.",
        )

    logger.info(
        "Appointment cancelled: id=%s by=%s",
        appointment_id,
        current_user.get("email"),
    )
    return CancelResponse(
        id=str(updated["_id"]),
        status=AppointmentStatus.CANCELLED,
    )


async def accept_appointment(appointment_id: str, current_user: Dict[str, Any]) -> AcceptResponse:
    if current_user.get("role") != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned doctor can accept an appointment.")
    appt = await appointment_crud.get_appointment_by_id(appointment_id)
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if appt.get("doctor_id") != str(current_user["_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This appointment is assigned to another doctor.")
    if appt.get("status") == AppointmentStatus.CANCELLED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancelled appointments cannot be accepted.")
    if appt.get("status") == AppointmentStatus.ACCEPTED.value:
        return AcceptResponse(id=appointment_id, status=AppointmentStatus.ACCEPTED, detail="Appointment is already accepted.")
    updated = await appointment_crud.accept_appointment(appointment_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment status changed. Please refresh and try again.")
    return AcceptResponse(id=str(updated["_id"]), status=AppointmentStatus.ACCEPTED)
