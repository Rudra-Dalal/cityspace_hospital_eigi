"""User document shape and helpers."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"


def user_document(
    *,
    first_name: str,
    last_name: str,
    email: str,
    mobile: str,
    password_hash: str,
    role: UserRole = UserRole.PATIENT,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.lower().strip(),
        "mobile": mobile.strip(),
        "password_hash": password_hash,
        "role": role.value,
        "created_at": now,
        "updated_at": now,
    }


def serialize_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Safe user payload — never includes password_hash."""
    return {
        "id": str(doc["_id"]),
        "first_name": doc["first_name"],
        "last_name": doc["last_name"],
        "email": doc["email"],
        "mobile": doc.get("mobile", ""),
        "role": doc["role"],
        "created_at": doc.get("created_at"),
    }
