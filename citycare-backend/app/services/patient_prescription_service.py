"""Shared patient prescription application service for listing and viewing prescriptions."""

from typing import Any, Dict, List, Optional
from app.cruds import prescription_crud, user_crud
from app.models.prescription_model import serialize_prescription
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _doctor_name(doctor: Dict[str, Any]) -> str:
    return f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()


async def get_patient_prescriptions(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieve all prescriptions belonging to a verified patient."""
    docs = await prescription_crud.get_for_patient(patient_id)
    results: List[Dict[str, Any]] = []
    for doc in docs:
        doctor = await user_crud.get_user_by_id(doc["doctor_id"])
        results.append(serialize_prescription(doc, doctor_name=_doctor_name(doctor or {})))
    return results


async def get_prescription_details(prescription_id: str, patient_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single prescription verifying patient ownership."""
    doc = await prescription_crud.get_by_id(prescription_id)
    if not doc:
        return None
    if doc.get("patient_id") != patient_id:
        return None  # Denied access

    doctor = await user_crud.get_user_by_id(doc["doctor_id"])
    return serialize_prescription(doc, doctor_name=_doctor_name(doctor or {}))
