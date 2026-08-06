"""Appointment business logic — booking gates, free slots, cancel."""

from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import VALID_SLOTS, get_settings
from app.cruds import appointment_crud
from app.models.appointment_model import (
    AppointmentStatus,
    appointment_document,
    serialize_appointment,
)
from app.schemas.appointment_schema import AppointmentCreate, AppointmentOut, CancelResponse
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


async def get_free_slots(date_str: str) -> Dict[str, Any]:
    validate_booking_date(date_str)
    booked = set(await appointment_crud.get_booked_slots_for_date(date_str))
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
    if current_user.get("role") != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can book appointments.",
        )

    validate_booking_date(payload.date)

    if payload.slot not in VALID_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid slot. Choose one of: {', '.join(VALID_SLOTS)}",
        )

    # Polite pre-check (helpful early answer)
    if await appointment_crud.slot_is_booked(payload.date, payload.slot):
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
        "Appointment booked: id=%s date=%s slot=%s patient=%s",
        created["_id"],
        created["date"],
        created["slot"],
        current_user.get("email"),
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

    # Ownership check — patients cancel only their own; doctors may cancel any
    is_owner = appt["patient_id"] == str(current_user["_id"])
    is_doctor = current_user.get("role") == "doctor"
    if not is_owner and not is_doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to cancel this appointment.",
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
