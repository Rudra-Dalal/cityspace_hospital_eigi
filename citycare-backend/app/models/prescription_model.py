"""Prescription document helpers."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def prescription_document(*, patient_id: str, doctor_id: str, hospital_id: str, appointment_id: str, diagnosis: str,
                          medicines: List[Dict[str, str]], general_instructions: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "patient_id": patient_id, "doctor_id": doctor_id, "hospital_id": hospital_id,
        "appointment_id": appointment_id,
        "diagnosis": diagnosis.strip(), "medicines": medicines,
        "general_instructions": general_instructions.strip(), "created_at": now, "updated_at": now,
        "pdf_url": None, "cloudinary_public_id": None,
    }


def serialize_prescription(doc: Dict[str, Any], *, doctor_name: str | None = None,
                           hospital: Optional[Dict[str, Any]] = None,
                           patient_name: str | None = None) -> Dict[str, Any]:
    payload = {"id": str(doc["_id"]), "patient_id": doc["patient_id"], "doctor_id": doc["doctor_id"],
               "hospital_id": doc.get("hospital_id"),
               "appointment_id": doc["appointment_id"], "diagnosis": doc["diagnosis"],
               "medicines": doc.get("medicines", []), "general_instructions": doc.get("general_instructions", ""),
               "created_at": doc.get("created_at"), "updated_at": doc.get("updated_at"),
               "pdf_url": doc.get("pdf_url"), "cloudinary_public_id": doc.get("cloudinary_public_id")}
    if doctor_name is not None:
        payload["doctor_name"] = doctor_name
    if patient_name is not None:
        payload["patient_name"] = patient_name
    if hospital is not None:
        payload["hospital_id"] = payload["hospital_id"] or str(hospital["_id"])
        payload["hospital"] = {
            "id": str(hospital["_id"]), "name": hospital.get("name", ""), "address": hospital.get("address"),
            "city": hospital.get("city"), "state": hospital.get("state"),
            "contact_phone": hospital.get("contact_phone"),
        }
    return payload
