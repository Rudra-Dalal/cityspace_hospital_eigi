"""Super Admin business logic — hospital & user management."""

from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import VALID_SLOTS
from app.core.security import hash_password
from app.cruds import hospital_crud, user_crud
from app.models.hospital_model import hospital_document, serialize_hospital
from app.models.user_model import UserRole, serialize_user, user_document
from app.schemas.hospital_schema import HospitalCreate, HospitalOut, HospitalUpdate
from app.schemas.user_schema import CreateDoctorRequest, CreateManagerRequest, UserOut
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Hospital management
# ---------------------------------------------------------------------------

async def create_hospital(payload: HospitalCreate, created_by: str) -> HospitalOut:
    doc = hospital_document(
        name=payload.name,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        facilities=payload.facilities,
        services=payload.services,
        working_hours=payload.working_hours,
        emergency_contact=payload.emergency_contact,
        status=payload.status or "active",
        created_by=created_by,
    )
    created = await hospital_crud.create_hospital(doc)
    logger.info("Hospital created: %s (status=%s by %s)", payload.name, doc["status"], created_by)
    return HospitalOut(**serialize_hospital(created))


async def list_hospitals(status: Optional[str] = None) -> List[HospitalOut]:
    hospitals = await hospital_crud.get_all_hospitals(status=status)
    return [HospitalOut(**serialize_hospital(h)) for h in hospitals]


async def update_hospital(hospital_id: str, payload: HospitalUpdate) -> HospitalOut:
    # Only send non-None fields to MongoDB
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update.")

    updated = await hospital_crud.update_hospital(hospital_id, updates)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    return HospitalOut(**serialize_hospital(updated))


# ---------------------------------------------------------------------------
# User management (super admin)
# ---------------------------------------------------------------------------

async def create_manager(payload: CreateManagerRequest, created_by: str) -> UserOut:
    """Super admin creates a hospital manager and assigns them to a hospital."""
    hospital = await hospital_crud.get_hospital_by_id(payload.hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    existing = await user_crud.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    doc = user_document(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        mobile=payload.mobile,
        password_hash=hash_password(payload.password),
        role=UserRole.HOSPITAL_MANAGER,
        hospital_id=payload.hospital_id,
        is_active=True,
    )
    try:
        created = await user_crud.create_user(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    logger.info("Hospital manager created: %s → hospital %s (by %s)", payload.email, payload.hospital_id, created_by)
    return UserOut(**serialize_user(created))


async def create_doctor(payload: CreateDoctorRequest, created_by: str) -> UserOut:
    """Super admin or manager creates a doctor and assigns them to a hospital."""
    hospital = await hospital_crud.get_hospital_by_id(payload.hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    existing = await user_crud.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    doc = user_document(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        mobile=payload.mobile,
        password_hash=hash_password(payload.password),
        role=UserRole.DOCTOR,
        hospital_id=payload.hospital_id,
        is_active=True,
        qualification=payload.qualification or "MBBS",
        specialization=payload.specialization or "General Physician",
        available_days=payload.available_days or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        working_hours=payload.working_hours or "10:00 - 20:00",
        valid_slots=payload.valid_slots or list(VALID_SLOTS),
    )

    try:
        created = await user_crud.create_user(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    logger.info("Doctor created: %s → hospital %s (by %s)", payload.email, payload.hospital_id, created_by)
    return UserOut(**serialize_user(created))


async def list_users(role: Optional[str] = None, hospital_id: Optional[str] = None) -> List[UserOut]:
    """List users with optional filters."""
    from app.core.database import get_database
    db = get_database()
    query: Dict[str, Any] = {}
    if role:
        query["role"] = role
    if hospital_id:
        query["hospital_id"] = hospital_id
    cursor = db.users.find(query, {"password_hash": 0}).sort("created_at", -1)
    users = [doc async for doc in cursor]
    return [UserOut(**serialize_user(u)) for u in users]


async def deactivate_user(user_id: str) -> UserOut:
    """Soft-deactivate a user by setting is_active=False."""
    from app.core.database import get_database
    from datetime import datetime, timezone
    db = get_database()
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID.")

    from pymongo import ReturnDocument
    updated = await db.users.find_one_and_update(
        {"_id": oid},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserOut(**serialize_user(updated))
