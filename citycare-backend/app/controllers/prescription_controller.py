"""Prescription business logic and authorization."""

from typing import Any, Dict, List
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError
from app.cruds import appointment_crud, prescription_crud, user_crud
from app.models.appointment_model import AppointmentStatus
from app.models.prescription_model import prescription_document, serialize_prescription
from app.schemas.prescription_schema import PrescriptionCreate, PrescriptionOut
from app.services.cloudinary_service import upload_prescription_pdf
from app.services.prescription_pdf import generate_prescription_pdf
from app.services.prescription_rag import index_prescription


def _doctor_name(doctor: Dict[str, Any]) -> str:
    return f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()


async def create(payload: PrescriptionCreate, current_user: Dict[str, Any]) -> PrescriptionOut:
    if current_user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can create prescriptions.")
    appointment = await appointment_crud.get_appointment_by_id(payload.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appointment.get("doctor_id") != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="This appointment is assigned to another doctor.")
    if appointment.get("status") != AppointmentStatus.ACCEPTED.value:
        raise HTTPException(status_code=400, detail="A prescription can only be created after the appointment is accepted.")
    patient = await user_crud.get_user_by_id(appointment["patient_id"])
    if not patient:
        raise HTTPException(status_code=404, detail="Appointment patient was not found.")
    document = prescription_document(
        patient_id=appointment["patient_id"],
        doctor_id=str(current_user["_id"]),
        appointment_id=payload.appointment_id,
        diagnosis=payload.diagnosis,
        medicines=[m.model_dump() for m in payload.medicines],
        general_instructions=payload.general_instructions,
    )
    try:
        # Generate/upload before persisting so a successful record always has a usable PDF URL.
        pdf = generate_prescription_pdf(document, appointment, current_user, patient)
        url, public_id = upload_prescription_pdf(pdf, payload.appointment_id)
        document["pdf_url"], document["cloudinary_public_id"] = url, public_id
        created = await prescription_crud.create_prescription(document)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A prescription already exists for this appointment.")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Prescription PDF storage is temporarily unavailable.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to create prescription.") from exc
    try:
        await index_prescription(created, _doctor_name(current_user))
    except Exception:
        # Retrieval index is derived data; source-of-truth prescription remains valid.
        pass
    return PrescriptionOut(**serialize_prescription(created, doctor_name=_doctor_name(current_user)))


async def get_one(prescription_id: str, current_user: Dict[str, Any]) -> PrescriptionOut:
    doc = await prescription_crud.get_by_id(prescription_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Prescription not found.")
    user_id, role = str(current_user["_id"]), current_user.get("role")

    if role in ("customer", "patient"):
        if doc["patient_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not have access to this prescription.")
    elif role == "doctor":
        if doc["doctor_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not have access to this prescription.")
    elif role == "hospital_manager":
        # Resolve appointment to verify hospital scope
        appointment = await appointment_crud.get_appointment_by_id(doc["appointment_id"])
        if not appointment or appointment.get("hospital_id") != current_user.get("hospital_id"):
            raise HTTPException(status_code=403, detail="You do not have access to prescriptions from another hospital.")
    elif role == "super_admin":
        pass  # Super admin is authorized for all platform prescriptions
    else:
        raise HTTPException(status_code=403, detail="You do not have access to this prescription.")

    doctor = await user_crud.get_user_by_id(doc["doctor_id"])
    return PrescriptionOut(**serialize_prescription(doc, doctor_name=_doctor_name(doctor or {})))


async def mine(current_user: Dict[str, Any]) -> List[PrescriptionOut]:
    if current_user.get("role") not in ("customer", "patient"):
        raise HTTPException(status_code=403, detail="Only patients can list their prescriptions.")
    docs = await prescription_crud.get_for_patient(str(current_user["_id"]))
    results = []
    for doc in docs:
        doctor = await user_crud.get_user_by_id(doc["doctor_id"])
        results.append(PrescriptionOut(**serialize_prescription(doc, doctor_name=_doctor_name(doctor or {}))))
    return results
