"""Hospital document shape and helpers."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def hospital_document(
    *,
    name: str,
    address: str,
    city: str,
    state: str,
    contact_phone: str,
    contact_email: str,
    facilities: Optional[List[str]] = None,
    services: Optional[List[str]] = None,
    working_hours: Optional[str] = "09:00 - 20:00",
    emergency_contact: Optional[str] = None,
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
        "facilities": [f.strip() for f in facilities if f.strip()] if facilities else [],
        "services": [s.strip() for s in services if s.strip()] if services else [],
        "working_hours": working_hours.strip() if working_hours else "09:00 - 20:00",
        "emergency_contact": emergency_contact.strip() if emergency_contact else contact_phone.strip(),
        "status": status.strip().lower() if status else "active",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def serialize_hospital(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "address": doc.get("address", ""),
        "city": doc.get("city", ""),
        "state": doc.get("state", ""),
        "contact_phone": doc.get("contact_phone", ""),
        "contact_email": doc.get("contact_email", ""),
        "facilities": doc.get("facilities", []),
        "services": doc.get("services", []),
        "working_hours": doc.get("working_hours", ""),
        "emergency_contact": doc.get("emergency_contact", ""),
        "status": doc.get("status", "active"),
        "created_by": doc.get("created_by"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
