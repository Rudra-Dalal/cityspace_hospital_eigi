"""Hospital document shape and helpers."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def hospital_document(
    *,
    name: str,
    address: str,
    city: str,
    state: str,
    contact_phone: str,
    contact_email: str,
    status: str = "active",
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "name": name.strip(),
        "address": address.strip(),
        "city": city.strip(),
        "state": state.strip(),
        "contact_phone": contact_phone.strip(),
        "contact_email": contact_email.lower().strip(),
        "status": "active",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def serialize_hospital(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "address": doc["address"],
        "city": doc["city"],
        "state": doc["state"],
        "contact_phone": doc["contact_phone"],
        "contact_email": doc["contact_email"],
        "status": doc["status"],
        "created_by": doc.get("created_by"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
