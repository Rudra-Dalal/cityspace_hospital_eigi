"""Appointment document shape and helpers."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AppointmentStatus(str, Enum):
    BOOKED = "booked"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"


def appointment_document(
    *,
    patient_id: str,
    hospital_id: str,
    doctor_id: str,
    date: str,
    slot: str,
    reason: str,
    temperature: Optional[float],
    symptoms: List[str],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "patient_id": patient_id,
        "hospital_id": hospital_id,
        "doctor_id": doctor_id,
        "date": date,
        "slot": slot,
        "reason": reason.strip(),
        "temperature": temperature,
        "symptoms": symptoms,
        "status": AppointmentStatus.BOOKED.value,
        "created_at": now,
        "updated_at": now,
    }


def serialize_appointment(
    doc: Dict[str, Any],
    *,
    patient_name: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "id": str(doc["_id"]),
        "patient_id": doc["patient_id"],
        "hospital_id": doc.get("hospital_id"),
        "doctor_id": doc.get("doctor_id"),
        "date": doc["date"],
        "slot": doc["slot"],
        "reason": doc["reason"],
        "temperature": doc.get("temperature"),
        "symptoms": doc.get("symptoms", []),
        "status": doc["status"],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    if patient_name is not None:
        payload["patient_name"] = patient_name
    return payload
