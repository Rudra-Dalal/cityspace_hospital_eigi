"""Auth business logic."""

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.security import create_access_token, hash_password, verify_password
from app.cruds import user_crud
from app.models.user_model import UserRole, serialize_user, user_document
from app.schemas.user_schema import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def signup(payload: SignupRequest) -> UserOut:
    """Public signup ALWAYS creates a customer — role from the body is ignored."""
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
        role=UserRole.CUSTOMER,  # never trust client-supplied role
        hospital_id=None,
    )

    try:
        created = await user_crud.create_user(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    logger.info("Customer signed up: %s", created["email"])
    return UserOut(**serialize_user(created))


async def login(payload: LoginRequest) -> TokenResponse:
    # Identical message for wrong email OR wrong password (no user enumeration)
    invalid_msg = "Incorrect email or password."
    user = await user_crud.get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        logger.warning("Authentication failed for email=%s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=invalid_msg,
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
    from app.core.config import get_settings

    settings = get_settings()

    # ------------------------------------------------------------------
    # Seed Doctor
    # ------------------------------------------------------------------
    existing_doctor = await user_crud.get_user_by_email(settings.doctor_email)
    if existing_doctor:
        if existing_doctor.get("role") != UserRole.DOCTOR.value:
            from app.core.database import get_database
            from datetime import datetime, timezone

            await get_database().users.update_one(
                {"_id": existing_doctor["_id"]},
                {
                    "$set": {
                        "role": UserRole.DOCTOR.value,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info("Updated existing user to doctor role: %s", settings.doctor_email)
        else:
            logger.info("Doctor account already present: %s", settings.doctor_email)
    else:
        doc = user_document(
            first_name=settings.doctor_first_name,
            last_name=settings.doctor_last_name,
            email=settings.doctor_email,
            mobile="+919999999999",
            password_hash=hash_password(settings.doctor_password),
            role=UserRole.DOCTOR,
            hospital_id=None,  # Will be set by migration
        )
        await user_crud.create_user(doc)
        logger.info("Seeded doctor account: %s", settings.doctor_email)

    # ------------------------------------------------------------------
    # Seed Super Admin
    # ------------------------------------------------------------------
    existing_admin = await user_crud.get_user_by_email(settings.super_admin_email)
    if existing_admin:
        if existing_admin.get("role") != UserRole.SUPER_ADMIN.value:
            from app.core.database import get_database
            from datetime import datetime, timezone

            await get_database().users.update_one(
                {"_id": existing_admin["_id"]},
                {
                    "$set": {
                        "role": UserRole.SUPER_ADMIN.value,
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
        )
        await user_crud.create_user(doc)
        logger.info("Seeded super admin account: %s", settings.super_admin_email)
