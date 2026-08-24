"""Auth business logic."""

from fastapi import HTTPException, status

from app.core.config import VALID_SLOTS, get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.cruds import user_crud
from app.models.user_model import UserRole, serialize_user, user_document
from app.schemas.user_schema import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.services import registration_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def signup(payload: SignupRequest) -> UserOut:
    """Public signup ALWAYS creates a customer account through the registration service."""
    created_user_dict = await registration_service.register_patient(payload)
    return UserOut(**created_user_dict)


async def login(payload: LoginRequest) -> TokenResponse:
    invalid_msg = "Incorrect email or password."
    user = await user_crud.get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        logger.warning("Authentication failed for email=%s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=invalid_msg,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is deactivated
    if user.get("is_active") is False:
        logger.warning("Deactivated user attempted login: email=%s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated. Please contact support.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        {
            "sub": str(user["_id"]),
            "email": user["email"],
            "role": user["role"],
            "hospital_id": user.get("hospital_id"),
        }
    )
    logger.info("User logged in: %s (role=%s)", user["email"], user["role"])
    return TokenResponse(
        access_token=token,
        user=UserOut(**serialize_user(user)),
    )


async def seed_doctor_if_missing() -> None:
    """Create the single seeded doctor + super-admin accounts if missing."""
    settings = get_settings()

    # ------------------------------------------------------------------
    # Seed Doctor
    # ------------------------------------------------------------------
    existing_doctor = await user_crud.get_user_by_email(settings.doctor_email)
    if existing_doctor:
        updates = {}
        if existing_doctor.get("role") != UserRole.DOCTOR.value:
            updates["role"] = UserRole.DOCTOR.value
        if existing_doctor.get("is_active") is None:
            updates["is_active"] = True
        if not existing_doctor.get("qualification"):
            updates["qualification"] = settings.doctor_qualification
        if not existing_doctor.get("specialization"):
            updates["specialization"] = "General Physician"
        if not existing_doctor.get("valid_slots"):
            updates["valid_slots"] = list(VALID_SLOTS)

        if updates:
            from datetime import datetime, timezone
            from app.core.database import get_database
            updates["updated_at"] = datetime.now(timezone.utc)
            await get_database().users.update_one(
                {"_id": existing_doctor["_id"]},
                {"$set": updates},
            )
            logger.info("Updated existing seeded doctor: %s", settings.doctor_email)
        else:
            logger.info("Doctor account already present and up to date: %s", settings.doctor_email)
    else:
        doc = user_document(
            first_name=settings.doctor_first_name,
            last_name=settings.doctor_last_name,
            email=settings.doctor_email,
            mobile="+919999999999",
            password_hash=hash_password(settings.doctor_password),
            role=UserRole.DOCTOR,
            hospital_id=None,  # Will be assigned by migration if missing
            is_active=True,
            qualification=settings.doctor_qualification,
            specialization="General Physician",
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            working_hours="10:00 - 20:00",
            slot_duration_minutes=settings.slot_duration_minutes,
            valid_slots=list(VALID_SLOTS),
        )
        await user_crud.create_user(doc)
        logger.info("Seeded doctor account: %s", settings.doctor_email)

    # ------------------------------------------------------------------
    # Seed Super Admin
    # ------------------------------------------------------------------
    existing_admin = await user_crud.get_user_by_email(settings.super_admin_email)
    if existing_admin:
        if existing_admin.get("role") != UserRole.SUPER_ADMIN.value or existing_admin.get("is_active") is None:
            from datetime import datetime, timezone
            from app.core.database import get_database

            await get_database().users.update_one(
                {"_id": existing_admin["_id"]},
                {
                    "$set": {
                        "role": UserRole.SUPER_ADMIN.value,
                        "is_active": True,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info("Updated existing user to super_admin role: %s", settings.super_admin_email)
        else:
            logger.info("Super admin account already present: %s", settings.super_admin_email)
    else:
        doc = user_document(
            first_name=settings.super_admin_first_name,
            last_name=settings.super_admin_last_name,
            email=settings.super_admin_email,
            mobile="+910000000000",
            password_hash=hash_password(settings.super_admin_password),
            role=UserRole.SUPER_ADMIN,
            hospital_id=None,
            is_active=True,
        )
        await user_crud.create_user(doc)
        logger.info("Seeded super admin account: %s", settings.super_admin_email)
