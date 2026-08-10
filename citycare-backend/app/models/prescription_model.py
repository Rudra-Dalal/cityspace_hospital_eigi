"""Prescription document helpers."""

from datetime import datetime, timezone
from typing import Any, Dict, List


def prescription_document(*, patient_id: str, doctor_id: str, appointment_id: str, diagnosis: str,
                          medicines: List[Dict[str, str]], general_instructions: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "patient_id": patient_id, "doctor_id": doctor_id, "appointment_id": appointment_id,
        "diagnosis": diagnosis.strip(), "medicines": medicines,
        "general_instructions": general_instructions.strip(), "created_at": now, "updated_at": now,
        "pdf_url": None, "cloudinary_public_id": None,
    }


def serialize_prescription(doc: Dict[str, Any], *, doctor_name: str | None = None) -> Dict[str, Any]:
    payload = {"id": str(doc["_id"]), "patient_id": doc["patient_id"], "doctor_id": doc["doctor_id"],
               "appointment_id": doc["appointment_id"], "diagnosis": doc["diagnosis"],
               "medicines": doc.get("medicines", []), "general_instructions": doc.get("general_instructions", ""),
               "created_at": doc.get("created_at"), "updated_at": doc.get("updated_at"),
               "pdf_url": doc.get("pdf_url"), "cloudinary_public_id": doc.get("cloudinary_public_id")}
    if doctor_name is not None:
        payload["doctor_name"] = doctor_name
    return payload
