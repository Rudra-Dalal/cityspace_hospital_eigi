"""Doctor / clinic business logic."""

from datetime import date as date_cls
from datetime import datetime, timezone

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


async def get_schedule(date_str: str) -> list[ScheduleItem]:
    try:
        date_cls.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date must be a valid ISO date YYYY-MM-DD",
        ) from exc

    appointments = await appointment_crud.get_appointments_for_date(date_str)
    patient_ids = list({a["patient_id"] for a in appointments})
    patients = await user_crud.get_users_by_ids(patient_ids)

    items: list[ScheduleItem] = []
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


async def get_stats() -> DoctorStatsResponse:
    today = datetime.now(timezone.utc).date().isoformat()
    total_patients = await user_crud.count_patients()
    today_visits = await appointment_crud.count_booked_for_date(today)
    upcoming_visits = await appointment_crud.count_upcoming_booked(today)
    return DoctorStatsResponse(
        total_patients=total_patients,
        today_visits=today_visits,
        upcoming_visits=upcoming_visits,
    )
