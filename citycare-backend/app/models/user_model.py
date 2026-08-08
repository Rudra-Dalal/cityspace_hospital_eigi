"""User document shape and helpers."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    HOSPITAL_MANAGER = "hospital_manager"
    DOCTOR = "doctor"
    CUSTOMER = "customer"   # renamed from "patient"


def user_document(
    *,
    first_name: str,
    last_name: str,
    email: str,
    mobile: str,
    password_hash: str,
    role: UserRole = UserRole.CUSTOMER,
    hospital_id: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc: Dict[str, Any] = {
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.lower().strip(),
        "mobile": mobile.strip(),
        "password_hash": password_hash,
        "role": role.value,
        "hospital_id": hospital_id,  # None for customer / super_admin
        "created_at": now,
        "updated_at": now,
    }
    return doc


def serialize_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Safe user payload — never includes password_hash."""
    return {
        "id": str(doc["_id"]),
        "first_name": doc["first_name"],
        "last_name": doc["last_name"],
        "email": doc["email"],
        "mobile": doc.get("mobile", ""),
        "role": doc["role"],
        "hospital_id": doc.get("hospital_id"),
        "created_at": doc.get("created_at"),
    }
