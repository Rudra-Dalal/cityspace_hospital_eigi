"""Reusable patient registration service."""

import re
from typing import Any, Dict, Optional, Union

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password
from app.cruds import user_crud
from app.models.user_model import UserRole, serialize_user, user_document
from app.schemas.user_schema import SignupRequest
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def register_patient(
    payload: Union[SignupRequest, Dict[str, Any]],
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

    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

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
        password_hash=hash_password(password),
        role=UserRole.CUSTOMER,  # Always customer for public signup
        hospital_id=None,
        is_active=True,
    )

    try:
        created = await user_crud.create_user(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    logger.info("Patient successfully registered: %s", created["email"])
    return serialize_user(created)
