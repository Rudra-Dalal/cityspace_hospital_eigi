"""Doctor / clinic business logic — now hospital-scoped."""

from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.core.config import VALID_SLOTS, get_settings
from app.cruds import appointment_crud, user_crud
from app.models.appointment_model import AppointmentStatus
from app.schemas.appointment_schema import (
    DoctorInfoResponse,
    DoctorStatsResponse,
    ScheduleItem,
)


def get_doctor_info() -> DoctorInfoResponse:
    settings = get_settings()
    return DoctorInfoResponse(
        name=settings.doctor_display_name,
        qualification=settings.doctor_qualification,
        clinic_name=settings.clinic_name,
        clinic_location=settings.clinic_location,
        morning_hours=settings.morning_hours,
        evening_hours=settings.evening_hours,
        slot_duration_minutes=settings.slot_duration_minutes,
        valid_slots=list(VALID_SLOTS),
    )


async def get_schedule(date_str: Optional[str], current_user: Dict[str, Any]) -> List[ScheduleItem]:
    if date_str is not None:
        try:
            date_cls.fromisoformat(date_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date must be a valid ISO date YYYY-MM-DD",
            ) from exc

    # Super admin can see all; doctor/manager scoped to their hospital
    doctor_id: Optional[str] = None
    hospital_id: Optional[str] = None

    role = current_user.get("role")
    if role == "doctor":
        doctor_id = str(current_user["_id"])
        hospital_id = current_user.get("hospital_id")
    elif role == "hospital_manager":
        hospital_id = current_user.get("hospital_id")
    # super_admin: no scoping

    if date_str is None:
        # No date provided — return all upcoming (today + future) appointments
        today = datetime.now(timezone.utc).date().isoformat()
        appointments = await appointment_crud.get_upcoming_appointments(
            today,
            doctor_id=doctor_id,
            hospital_id=hospital_id,
        )
    else:
        appointments = await appointment_crud.get_appointments_for_date(
            date_str,
            doctor_id=doctor_id,
            hospital_id=hospital_id,
        )
    patient_ids = list({a["patient_id"] for a in appointments})
    patients = await user_crud.get_users_by_ids(patient_ids)

    items: List[ScheduleItem] = []
    for appt in appointments:
        patient = patients.get(appt["patient_id"])
        name = (
            f"{patient['first_name']} {patient['last_name']}"
            if patient
            else "Unknown patient"
        )
        items.append(
            ScheduleItem(
                id=str(appt["_id"]),
                slot=appt["slot"],
                date=appt["date"],
                patient_name=name,
                reason=appt["reason"],
                temperature=appt.get("temperature"),
                symptoms=appt.get("symptoms", []),
                status=AppointmentStatus(appt["status"]),
            )
        )
    return items


async def get_stats(current_user: Dict[str, Any]) -> DoctorStatsResponse:
    today = datetime.now(timezone.utc).date().isoformat()

    role = current_user.get("role")
    doctor_id: Optional[str] = None
    hospital_id: Optional[str] = None

    if role == "doctor":
        doctor_id = str(current_user["_id"])
        hospital_id = current_user.get("hospital_id")
    elif role == "hospital_manager":
        hospital_id = current_user.get("hospital_id")

    total_patients = await user_crud.count_patients()
    today_visits = await appointment_crud.count_booked_for_date(today, doctor_id=doctor_id, hospital_id=hospital_id)
    upcoming_visits = await appointment_crud.count_upcoming_booked(today, doctor_id=doctor_id, hospital_id=hospital_id)

    return DoctorStatsResponse(
        total_patients=total_patients,
        today_visits=today_visits,
        upcoming_visits=upcoming_visits,
    )
