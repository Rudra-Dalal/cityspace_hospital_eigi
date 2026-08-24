"""User document shape and helpers."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    HOSPITAL_MANAGER = "hospital_manager"
    DOCTOR = "doctor"
    CUSTOMER = "customer"


def user_document(
    *,
    first_name: str,
    last_name: str,
    email: str,
    mobile: str,
    password_hash: str,
    role: UserRole = UserRole.CUSTOMER,
    hospital_id: Optional[str] = None,
    is_active: bool = True,
    qualification: Optional[str] = None,
    specialization: Optional[str] = None,
    available_days: Optional[List[str]] = None,
    working_hours: Optional[str] = None,
    slot_duration_minutes: Optional[int] = 30,
    valid_slots: Optional[List[str]] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc: Dict[str, Any] = {
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.lower().strip(),
        "mobile": mobile.strip(),
        "password_hash": password_hash,
        "role": role.value if isinstance(role, UserRole) else str(role),
        "hospital_id": hospital_id,
        "is_active": is_active,
        "created_at": now,
        "updated_at": now,
    }
    if qualification is not None:
        doc["qualification"] = qualification.strip()
    if specialization is not None:
        doc["specialization"] = specialization.strip()
    if available_days is not None:
        doc["available_days"] = available_days
    if working_hours is not None:
        doc["working_hours"] = working_hours.strip()
    if slot_duration_minutes is not None:
        doc["slot_duration_minutes"] = slot_duration_minutes
    if valid_slots is not None:
        doc["valid_slots"] = valid_slots

    return doc


def serialize_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Safe user payload — never includes password_hash."""
    payload: Dict[str, Any] = {
        "id": str(doc["_id"]),
        "first_name": doc["first_name"],
        "last_name": doc["last_name"],
        "email": doc["email"],
        "mobile": doc.get("mobile", ""),
        "role": doc["role"],
        "hospital_id": doc.get("hospital_id"),
        "is_active": doc.get("is_active", True),
        "created_at": doc.get("created_at"),
    }
    if "qualification" in doc:
        payload["qualification"] = doc["qualification"]
    if "specialization" in doc:
        payload["specialization"] = doc["specialization"]
    if "available_days" in doc:
        payload["available_days"] = doc["available_days"]
    if "working_hours" in doc:
        payload["working_hours"] = doc["working_hours"]
    if "slot_duration_minutes" in doc:
        payload["slot_duration_minutes"] = doc["slot_duration_minutes"]
    if "valid_slots" in doc:
        payload["valid_slots"] = doc["valid_slots"]
    return payload
