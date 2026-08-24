"""Patient-safe discovery controller for hospitals and doctors."""

from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.core.config import VALID_SLOTS, get_settings
from app.core.database import get_database
from app.cruds import appointment_crud, hospital_crud, user_crud
from app.models.hospital_model import serialize_hospital
from app.models.user_model import serialize_user
from app.schemas.hospital_schema import HospitalOut
from app.schemas.user_schema import DoctorAvailabilityOut, DoctorPublicOut
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_AVAILABLE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _validate_booking_window(date_str: str) -> date_cls:
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
            detail="Cannot check availability for past dates.",
        )
    if target > max_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointments can only be booked up to {settings.booking_window_days} days ahead.",
        )
    return target


async def list_active_hospitals() -> List[HospitalOut]:
    """Return all active hospitals with facilities, services, and operational info."""
    hospitals = await hospital_crud.get_all_hospitals(status="active")
    return [HospitalOut(**serialize_hospital(h)) for h in hospitals]


async def get_hospital_details(hospital_id: str) -> HospitalOut:
    """Return details for a single active hospital. 404 if not found or inactive."""
    hospital = await hospital_crud.get_hospital_by_id(hospital_id)
    if not hospital or hospital.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found or is currently inactive.",
        )
    return HospitalOut(**serialize_hospital(hospital))


async def list_active_doctors(
    specialization: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> List[DoctorPublicOut]:
    """
    Return active doctors. Optional filters: specialization, hospital_id.
    Doctors must belong to an active hospital (if assigned) and have is_active=True.
    """
    db = get_database()
    query: Dict[str, Any] = {
        "role": "doctor",
        "is_active": {"$ne": False},
    }
    if specialization:
        query["specialization"] = {"$regex": f"^{specialization.strip()}$", "$options": "i"}
    if hospital_id:
        query["hospital_id"] = hospital_id.strip()

    cursor = db.users.find(query, {"password_hash": 0}).sort("first_name", 1)
    raw_doctors = [doc async for doc in cursor]

    # Pre-fetch hospital names
    hospital_ids = list({d.get("hospital_id") for d in raw_doctors if d.get("hospital_id")})
    hospital_map: Dict[str, Dict[str, Any]] = {}
    if hospital_ids:
        for hid in hospital_ids:
            h = await hospital_crud.get_hospital_by_id(hid)
            if h and h.get("status") == "active":
                hospital_map[hid] = h

    results: List[DoctorPublicOut] = []
    for d in raw_doctors:
        hid = d.get("hospital_id")
        # If doctor belongs to a hospital, verify hospital is active
        if hid and hid not in hospital_map:
            continue

        h_name = hospital_map[hid]["name"] if hid in hospital_map else None
        valid_slots = d.get("valid_slots") or list(VALID_SLOTS)
        available_days = d.get("available_days") or DEFAULT_AVAILABLE_DAYS
        working_hours = d.get("working_hours") or "10:00 - 20:00"

        results.append(
            DoctorPublicOut(
                id=str(d["_id"]),
                first_name=d.get("first_name", ""),
                last_name=d.get("last_name", ""),
                email=d.get("email", ""),
                mobile=d.get("mobile", ""),
                role="doctor",
                qualification=d.get("qualification", "MBBS"),
                specialization=d.get("specialization", "General Physician"),
                hospital_id=hid,
                hospital_name=h_name,
                is_active=d.get("is_active", True),
                available_days=available_days,
                working_hours=working_hours,
                slot_duration_minutes=d.get("slot_duration_minutes", 30),
                valid_slots=valid_slots,
            )
        )

    return results


async def get_doctor_details(doctor_id: str) -> DoctorPublicOut:
    """Return public details for an active doctor."""
    user = await user_crud.get_user_by_id(doctor_id)
    if not user or user.get("role") != "doctor" or user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found or is currently inactive.",
        )

    hid = user.get("hospital_id")
    h_name = None
    if hid:
        hospital = await hospital_crud.get_hospital_by_id(hid)
        if not hospital or hospital.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor's assigned hospital is currently inactive.",
            )
        h_name = hospital.get("name")

    valid_slots = user.get("valid_slots") or list(VALID_SLOTS)
    available_days = user.get("available_days") or DEFAULT_AVAILABLE_DAYS
    working_hours = user.get("working_hours") or "10:00 - 20:00"

    return DoctorPublicOut(
        id=str(user["_id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        email=user.get("email", ""),
        mobile=user.get("mobile", ""),
        role="doctor",
        qualification=user.get("qualification", "MBBS"),
        specialization=user.get("specialization", "General Physician"),
        hospital_id=hid,
        hospital_name=h_name,
        is_active=user.get("is_active", True),
        available_days=available_days,
        working_hours=working_hours,
        slot_duration_minutes=user.get("slot_duration_minutes", 30),
        valid_slots=valid_slots,
    )


async def get_doctor_availability(doctor_id: str, date_str: str) -> DoctorAvailabilityOut:
    """
    Compute doctor-specific available appointment slots on a given date.
    
    Strategy:
    1. Validate date within booking window.
    2. Verify doctor and doctor's hospital are active.
    3. Determine weekday from date; check doctor's available_days schedule.
    4. Fetch doctor's valid slots for their working hours.
    5. Exclude already booked/accepted appointments.
    """
    target_date = _validate_booking_window(date_str)
    doctor = await get_doctor_details(doctor_id)

    day_of_week = target_date.strftime("%A")
    available_days = doctor.available_days or DEFAULT_AVAILABLE_DAYS

    if day_of_week not in available_days:
        return DoctorAvailabilityOut(
            doctor_id=doctor.id,
            hospital_id=doctor.hospital_id,
            date=date_str,
            day_of_week=day_of_week,
            is_available=False,
            available_slots=[],
            all_slots=[],
            message=f"Doctor is not available on {day_of_week}s.",
        )

    all_slots = doctor.valid_slots or list(VALID_SLOTS)
    booked_slots = set(
        await appointment_crud.get_booked_slots_for_date(
            date_str,
            doctor_id=doctor.id,
            hospital_id=doctor.hospital_id,
        )
    )

    free_slots = [s for s in all_slots if s not in booked_slots]

    return DoctorAvailabilityOut(
        doctor_id=doctor.id,
        hospital_id=doctor.hospital_id,
        date=date_str,
        day_of_week=day_of_week,
        is_available=True,
        available_slots=free_slots,
        all_slots=all_slots,
        message="Available" if free_slots else "All slots booked for this date.",
    )
