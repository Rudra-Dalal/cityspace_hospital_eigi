"""MongoDB queries for prescriptions and their patient-scoped retrieval records."""

from typing import Any, Dict, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from app.core.database import get_database


async def create_prescription(document: Dict[str, Any]) -> Dict[str, Any]:
    result = await get_database().prescriptions.insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def get_by_id(prescription_id: str) -> Optional[Dict[str, Any]]:
    try: oid = ObjectId(prescription_id)
    except InvalidId: return None
    return await get_database().prescriptions.find_one({"_id": oid})


async def set_pdf(prescription_id: Any, pdf_url: str, cloudinary_public_id: str) -> None:
    await get_database().prescriptions.update_one(
        {"_id": prescription_id},
        {"$set": {"pdf_url": pdf_url, "cloudinary_public_id": cloudinary_public_id}},
    )


async def delete_prescription(prescription_id: Any) -> None:
    await get_database().prescriptions.delete_one({"_id": prescription_id})


async def get_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    cursor = get_database().prescriptions.find({"patient_id": patient_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def get_for_doctor(doctor_id: str) -> List[Dict[str, Any]]:
    cursor = get_database().prescriptions.find({"doctor_id": doctor_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def add_vector_record(document: Dict[str, Any]) -> None:
    await get_database().prescription_vectors.update_one(
        {"prescription_id": document["prescription_id"], "patient_id": document["patient_id"]},
        {"$set": document}, upsert=True,
    )


async def get_vector_records_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    cursor = get_database().prescription_vectors.find({"patient_id": patient_id}).sort("created_at", -1)
    return [doc async for doc in cursor]
