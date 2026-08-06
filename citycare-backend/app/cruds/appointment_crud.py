"""Appointment database queries."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.models.appointment_model import AppointmentStatus


async def create_appointment(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a booked appointment.
    Raises DuplicateKeyError if (date, slot) is already booked — the steel door.
    """
    db = get_database()
    result = await db.appointments.insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def get_booked_slots_for_date(date: str) -> List[str]:
    db = get_database()
    cursor = db.appointments.find(
        {"date": date, "status": AppointmentStatus.BOOKED.value},
        {"slot": 1},
    )
    return [doc["slot"] async for doc in cursor]


async def slot_is_booked(date: str, slot: str) -> bool:
    db = get_database()
    existing = await db.appointments.find_one(
        {"date": date, "slot": slot, "status": AppointmentStatus.BOOKED.value}
    )
    return existing is not None


async def get_appointments_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    db = get_database()
    cursor = db.appointments.find({"patient_id": patient_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def get_appointments_for_date(date: str) -> List[Dict[str, Any]]:
    db = get_database()
    cursor = db.appointments.find({"date": date}).sort("slot", 1)
    return [doc async for doc in cursor]


async def count_booked_for_date(date: str) -> int:
    db = get_database()
    return await db.appointments.count_documents(
        {"date": date, "status": AppointmentStatus.BOOKED.value}
    )


async def count_upcoming_booked(from_date: str) -> int:
    """Booked appointments on from_date or later (inclusive)."""
    db = get_database()
    return await db.appointments.count_documents(
        {
            "date": {"$gte": from_date},
            "status": AppointmentStatus.BOOKED.value,
        }
    )


async def get_appointment_by_id(appointment_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(appointment_id)
    except InvalidId:
        return None
    return await db.appointments.find_one({"_id": oid})


async def cancel_appointment(appointment_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(appointment_id)
    except InvalidId:
        return None
    now = datetime.now(timezone.utc)
    result = await db.appointments.find_one_and_update(
        {"_id": oid, "status": AppointmentStatus.BOOKED.value},
        {
            "$set": {
                "status": AppointmentStatus.CANCELLED.value,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    return result
