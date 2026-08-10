"""Patient-scoped prescription retrieval. Structured prescription data is the source of truth."""

import re
import hashlib
import math
from datetime import datetime, timezone
from typing import Any, Dict, List
from app.cruds import prescription_crud


def searchable_text(prescription: Dict[str, Any], doctor_name: str = "") -> str:
    medicines = "\n".join(f"Medicine: {m['name']}; Dosage: {m['dosage']}; Frequency: {m['frequency']}; Duration: {m['duration']}; Instructions: {m.get('instructions', '')}" for m in prescription["medicines"])
    return f"Doctor: {doctor_name}\nPrescription date: {prescription['created_at'].isoformat()}\nDiagnosis: {prescription['diagnosis']}\n{medicines}\nGeneral instructions: {prescription.get('general_instructions', '')}"


def _embed(text: str, dimensions: int = 128) -> List[float]:
    """Local deterministic embedding so prescription retrieval works without another service."""
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % dimensions
        vector[index] += 1.0
    magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / magnitude for value in vector]


def _similarity(left: List[float], right: List[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


async def index_prescription(prescription: Dict[str, Any], doctor_name: str = "") -> None:
    text = searchable_text(prescription, doctor_name)
    await prescription_crud.add_vector_record({
        "patient_id": prescription["patient_id"], "prescription_id": str(prescription["_id"]),
        "doctor_id": prescription["doctor_id"], "appointment_id": prescription["appointment_id"],
        "document_type": "prescription", "text": text,
        "embedding": _embed(text), "created_at": datetime.now(timezone.utc),
    })


async def retrieve_for_patient(patient_id: str, question: str, limit: int = 3) -> List[Dict[str, Any]]:
    # The patient predicate is applied in MongoDB before any ranking; never accept a caller-provided patient id.
    records = await prescription_crud.get_vector_records_for_patient(patient_id)
    question_embedding = _embed(question)
    def score(item: Dict[str, Any]) -> float:
        return _similarity(question_embedding, item.get("embedding") or _embed(item.get("text", "")))
    return sorted(records, key=score, reverse=True)[:limit]
