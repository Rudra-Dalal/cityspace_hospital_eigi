"""Hospital Manager business logic."""

from typing import Any, Dict, List

from fastapi import HTTPException, status

from app.cruds import hospital_crud
from app.models.hospital_model import serialize_hospital
from app.schemas.hospital_schema import HospitalManagerUpdate, HospitalOut
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_my_hospital(manager: Dict[str, Any]) -> HospitalOut:
    hospital_id = manager.get("hospital_id")
    if not hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is not assigned to a hospital.",
        )
    hospital = await hospital_crud.get_hospital_by_id(hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found.")
    return HospitalOut(**serialize_hospital(hospital))


async def update_my_hospital(manager: Dict[str, Any], payload: HospitalManagerUpdate) -> HospitalOut:
    hospital_id = manager.get("hospital_id")
    if not hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is not assigned to a hospital.",
        )
    # Exclude status from manager updates (only admins can change status)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None and k != "status"}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update.")

    updated = await hospital_crud.update_hospital(hospital_id, updates)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found.")
    return HospitalOut(**serialize_hospital(updated))


async def get_my_doctors(manager: Dict[str, Any]) -> List[Dict[str, Any]]:
    from app.core.database import get_database
    from app.models.user_model import serialize_user
    db = get_database()
    hospital_id = manager.get("hospital_id")
    if not hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is not assigned to a hospital.",
        )
    cursor = db.users.find(
        {"hospital_id": hospital_id, "role": "doctor"},
        {"password_hash": 0}
    ).sort("first_name", 1)
    doctors = [doc async for doc in cursor]
    return [serialize_user(d) for d in doctors]


async def update_doctor(manager: Dict[str, Any], doctor_id: str, payload: Any) -> Dict[str, Any]:
    """Hospital manager updates doctor profile/availability within their hospital."""
    hospital_id = manager.get("hospital_id")
    if not hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is not assigned to a hospital.",
        )
    from bson import ObjectId
    from app.core.database import get_database
    from app.models.user_model import serialize_user
    from datetime import datetime, timezone
    from pymongo import ReturnDocument
    db = get_database()
    try:
        oid = ObjectId(doctor_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID.")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update.")
    updates["updated_at"] = datetime.now(timezone.utc)

    updated = await db.users.find_one_and_update(
        {"_id": oid, "hospital_id": hospital_id, "role": "doctor"},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found in your hospital.")
    return serialize_user(updated)


async def get_my_appointments(manager: Dict[str, Any]) -> List[Dict[str, Any]]:
    from app.core.database import get_database
    from app.models.appointment_model import serialize_appointment
    db = get_database()
    hospital_id = manager.get("hospital_id")
    if not hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is not assigned to a hospital.",
        )
    cursor = db.appointments.find({"hospital_id": hospital_id}).sort("created_at", -1)
    appointments = [doc async for doc in cursor]
    return [serialize_appointment(a) for a in appointments]
