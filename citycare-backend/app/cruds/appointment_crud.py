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
    Raises DuplicateKeyError if (hospital_id, doctor_id, date, slot) is already booked.
    """
    db = get_database()
    result = await db.appointments.insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def get_booked_slots_for_date(
    date: str,
    doctor_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> List[str]:
    db = get_database()
    query: Dict[str, Any] = {"date": date, "status": AppointmentStatus.BOOKED.value}
    if doctor_id:
        query["doctor_id"] = doctor_id
    if hospital_id:
        query["hospital_id"] = hospital_id
    cursor = db.appointments.find(query, {"slot": 1})
    return [doc["slot"] async for doc in cursor]


async def slot_is_booked(
    date: str,
    slot: str,
    doctor_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> bool:
    db = get_database()
    query: Dict[str, Any] = {
        "date": date,
        "slot": slot,
        "status": AppointmentStatus.BOOKED.value,
    }
    if doctor_id:
        query["doctor_id"] = doctor_id
    if hospital_id:
        query["hospital_id"] = hospital_id
    existing = await db.appointments.find_one(query)
    return existing is not None


async def get_appointments_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    db = get_database()
    cursor = db.appointments.find({"patient_id": patient_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def get_appointments_for_date(
    date: str,
    doctor_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    db = get_database()
    query: Dict[str, Any] = {"date": date}
    if doctor_id:
        query["doctor_id"] = doctor_id
    if hospital_id:
        query["hospital_id"] = hospital_id
    cursor = db.appointments.find(query).sort("slot", 1)
    return [doc async for doc in cursor]


async def count_booked_for_date(
    date: str,
    doctor_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> int:
    db = get_database()
    query: Dict[str, Any] = {"date": date, "status": AppointmentStatus.BOOKED.value}
    if doctor_id:
        query["doctor_id"] = doctor_id
    if hospital_id:
        query["hospital_id"] = hospital_id
    return await db.appointments.count_documents(query)


async def count_upcoming_booked(
    from_date: str,
    doctor_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
) -> int:
    """Booked appointments on from_date or later (inclusive)."""
    db = get_database()
    query: Dict[str, Any] = {
        "date": {"$gte": from_date},
        "status": AppointmentStatus.BOOKED.value,
    }
    if doctor_id:
        query["doctor_id"] = doctor_id
    if hospital_id:
        query["hospital_id"] = hospital_id
    return await db.appointments.count_documents(query)


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
