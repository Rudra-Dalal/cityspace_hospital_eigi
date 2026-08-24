"""Reusable patient registration service with consent tracking and secure activation."""

import hashlib
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple, Union

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.database import get_database
from app.core.security import hash_password
from app.cruds import user_crud
from app.models.user_model import UserRole, serialize_user, user_document
from app.schemas.user_schema import SignupRequest
from app.utils.logger import get_logger

logger = get_logger(__name__)


def hash_token(token: str) -> str:
    """Hash a token with SHA-256 for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_account_activation_token(patient_id: str, ttl_hours: int = 48) -> str:
    """Generate a one-time secure web password setup token."""
    db = get_database()
    raw_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)

    # Invalidate any older activation tokens for this patient
    await db.account_activation_tokens.delete_many({"patient_id": patient_id})

    await db.account_activation_tokens.insert_one({
        "token_hash": token_h,
        "patient_id": patient_id,
        "purpose": "password_setup",
        "expires_at": expires_at,
        "used_at": None,
        "created_at": now,
    })
    return raw_token


async def verify_and_consume_activation_token(token: str) -> Optional[str]:
    """
    Verify an activation token and mark it as consumed.
    Returns patient_id if valid, None otherwise.
    """
    db = get_database()
    token_h = hash_token(token)
    now = datetime.now(timezone.utc)

    record = await db.account_activation_tokens.find_one_and_update(
        {
            "token_hash": token_h,
            "expires_at": {"$gt": now},
            "used_at": None,
        },
        {"$set": {"used_at": now}},
    )
    if not record:
        return None
    return record.get("patient_id")


async def register_patient(
    payload: Union[SignupRequest, Dict[str, Any]],
    consent: Optional[Dict[str, Any]] = None,
    allow_activation_token: bool = False,
) -> Dict[str, Any]:
    """
    Validate, normalize, and register a new patient/customer account.
    
    Guarantees:
    - Normalizes names (trimmed), email (trimmed + lowercase), mobile (trimmed).
    - Validates minimum requirements.
    - Prevents duplicate registration.
    - Public registration ALWAYS creates a customer role (never privileged).
    - Always creates active accounts (is_active=True).
    - Returns safe serialized user data (never exposes passwords or hashes).
    """
    if isinstance(payload, SignupRequest):
        first_name = payload.first_name.strip()
        last_name = payload.last_name.strip()
        email = payload.email.lower().strip()
        mobile = payload.mobile.strip()
        password = payload.password
    elif isinstance(payload, dict):
        first_name = str(payload.get("first_name", "")).strip()
        last_name = str(payload.get("last_name", "")).strip()
        email = str(payload.get("email", "")).lower().strip()
        mobile = str(payload.get("mobile", "")).strip()
        password = str(payload.get("password", ""))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid registration payload.",
        )

    if not first_name or not last_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="First name and last name are required.",
        )

    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email address is required.",
        )

    if not re.fullmatch(r"\+91[6-9]\d{9}", mobile):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mobile must match +91 followed by a 10-digit Indian number.",
        )

    if not password and allow_activation_token:
        # Generate random temporary password hash for token-based activation
        pwd_hash = hash_password(secrets.token_urlsafe(24))
    else:
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long.",
            )
        pwd_hash = hash_password(password)

    # Check for existing account
    existing = await user_crud.get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    doc = user_document(
        first_name=first_name,
        last_name=last_name,
        email=email,
        mobile=mobile,
        password_hash=pwd_hash,
        role=UserRole.CUSTOMER,  # Always customer for public signup
        hospital_id=None,
        is_active=True,
    )

    if consent:
        doc["consent"] = consent

    try:
        created = await user_crud.create_user(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    patient_id = str(created["_id"])
    logger.info("Patient successfully registered: %s (ID: %s)", created["email"], patient_id)

    serialized = serialize_user(created)

    if allow_activation_token:
        act_token = await create_account_activation_token(patient_id)
        settings = get_settings()
        serialized["activation_token"] = act_token
        serialized["activation_url"] = f"{settings.telegram_web_app_url.rstrip('/')}/set-password?token={act_token}"

    return serialized
