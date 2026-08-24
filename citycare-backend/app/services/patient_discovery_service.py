"""Shared patient discovery application service for hospitals, doctors, and real-time availability."""

from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import zoneinfo

from app.core.config import VALID_SLOTS, get_settings
from app.core.database import get_database
from app.cruds import appointment_crud, hospital_crud, user_crud
from app.models.hospital_model import serialize_hospital
from app.models.user_model import serialize_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_AVAILABLE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def get_current_date_in_tz(tz_name: str = "Asia/Kolkata") -> date_cls:
    """Get current calendar date in the specified hospital timezone."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
        return datetime.now(tz).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def validate_booking_date(date_str: str, tz_name: str = "Asia/Kolkata") -> date_cls:
    """
    Validate ISO date string YYYY-MM-DD against current date and rolling booking window.
    Raises ValueError on invalid formats or range violations.
    """
    settings = get_settings()
    try:
        target = date_cls.fromisoformat(date_str.strip())
    except Exception as exc:
        raise ValueError("date must be a valid ISO date YYYY-MM-DD") from exc

    today = get_current_date_in_tz(tz_name)
    max_date = today.fromordinal(today.toordinal() + settings.booking_window_days)

    if target < today:
        raise ValueError("Cannot select or book dates in the past.")
    if target > max_date:
        raise ValueError(f"Appointments can only be booked up to {settings.booking_window_days} days ahead.")
    return target


async def list_active_hospitals() -> List[Dict[str, Any]]:
    """Return all active hospital branches with facilities and contact info."""
    raw_hospitals = await hospital_crud.get_all_hospitals(status="active")
    return [serialize_hospital(h) for h in raw_hospitals]


async def get_hospital_details(hospital_id: str) -> Optional[Dict[str, Any]]:
    """Return details for a single active hospital. None if not found or inactive."""
    hospital = await hospital_crud.get_hospital_by_id(hospital_id)
    if not hospital or hospital.get("status") != "active":
        return None
    return serialize_hospital(hospital)


async def list_active_doctors(
    specialization: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return active doctors with hospital name resolution. Optional filters: specialization, hospital_id."""
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

    # Resolve hospital names
    hospital_ids = list({d.get("hospital_id") for d in raw_doctors if d.get("hospital_id")})
    hospital_map: Dict[str, Dict[str, Any]] = {}
    if hospital_ids:
        for hid in hospital_ids:
            h = await hospital_crud.get_hospital_by_id(hid)
            if h and h.get("status") == "active":
                hospital_map[hid] = h

    results: List[Dict[str, Any]] = []
    for d in raw_doctors:
        hid = d.get("hospital_id")
        h_info = hospital_map.get(hid) if hid else None
        # If doctor assigned to inactive hospital, skip
        if hid and not h_info:
            continue

        item = {
            "id": str(d["_id"]),
            "first_name": d.get("first_name", ""),
            "last_name": d.get("last_name", ""),
            "email": d.get("email", ""),
            "mobile": d.get("mobile", ""),
            "specialization": d.get("specialization"),
            "qualification": d.get("qualification"),
            "experience_years": d.get("experience_years"),
            "consultation_fee": d.get("consultation_fee"),
            "hospital_id": hid,
            "hospital_name": h_info.get("name") if h_info else None,
            "hospital_city": h_info.get("city") if h_info else None,
            "available_days": d.get("available_days") or DEFAULT_AVAILABLE_DAYS,
            "working_hours": d.get("working_hours") or "09:00 - 17:00",
            "is_active": d.get("is_active", True),
        }
        results.append(item)
    return results


async def get_doctor_details(doctor_id: str) -> Optional[Dict[str, Any]]:
    """Return public profile of a single active doctor. None if not found or inactive."""
    doctor = await user_crud.get_user_by_id(doctor_id)
    if not doctor or doctor.get("role") != "doctor" or doctor.get("is_active") is False:
        return None

    hid = doctor.get("hospital_id")
    h_info = None
    if hid:
        h_info = await hospital_crud.get_hospital_by_id(hid)
        if not h_info or h_info.get("status") != "active":
            return None

    return {
        "id": str(doctor["_id"]),
        "first_name": doctor.get("first_name", ""),
        "last_name": doctor.get("last_name", ""),
        "email": doctor.get("email", ""),
        "mobile": doctor.get("mobile", ""),
        "specialization": doctor.get("specialization"),
        "qualification": doctor.get("qualification"),
        "experience_years": doctor.get("experience_years"),
        "consultation_fee": doctor.get("consultation_fee"),
        "hospital_id": hid,
        "hospital_name": h_info.get("name") if h_info else None,
        "hospital_city": h_info.get("city") if h_info else None,
        "available_days": doctor.get("available_days") or DEFAULT_AVAILABLE_DAYS,
        "working_hours": doctor.get("working_hours") or "09:00 - 17:00",
        "is_active": doctor.get("is_active", True),
    }


async def get_doctor_availability(
    doctor_id: str,
    date_str: str,
    tz_name: str = "Asia/Kolkata",
) -> Dict[str, Any]:
    """
    Compute doctor availability for a target date.
    Subtracts active bookings from doctor-specific valid slots.
    Raises ValueError on invalid target dates or inactive doctor.
    """
    target_date = validate_booking_date(date_str, tz_name=tz_name)
    weekday_name = target_date.strftime("%A")

    doctor = await user_crud.get_user_by_id(doctor_id)
    if not doctor or doctor.get("role") != "doctor" or doctor.get("is_active") is False:
        raise ValueError("Doctor not found or is currently inactive.")

    hid = doctor.get("hospital_id")
    if hid:
        hospital = await hospital_crud.get_hospital_by_id(hid)
        if not hospital or hospital.get("status") != "active":
            raise ValueError("Doctor belongs to an inactive hospital.")

    available_days = doctor.get("available_days") or DEFAULT_AVAILABLE_DAYS
    valid_slots = doctor.get("valid_slots") or list(VALID_SLOTS)

    doctor_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()

    if weekday_name not in available_days:
        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor_name,
            "date": date_str,
            "weekday": weekday_name,
            "is_available": False,
            "working_hours": doctor.get("working_hours") or "09:00 - 17:00",
            "available_slots": [],
            "booked_slots": [],
        }

    booked_slots = await appointment_crud.get_booked_slots_for_date(
        date_str,
        doctor_id=doctor_id,
        hospital_id=hid,
    )
    booked_set = set(booked_slots)
    free_slots = [slot for slot in valid_slots if slot not in booked_set]

    return {
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "date": date_str,
        "weekday": weekday_name,
        "is_available": len(free_slots) > 0,
        "working_hours": doctor.get("working_hours") or "09:00 - 17:00",
        "available_slots": free_slots,
        "booked_slots": booked_slots,
    }
