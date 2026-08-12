"""Prescription business logic and authorization."""

from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Response
from pymongo.errors import DuplicateKeyError
from app.cruds import appointment_crud, hospital_crud, prescription_crud, user_crud
from app.models.appointment_model import AppointmentStatus
from app.models.prescription_model import prescription_document, serialize_prescription
from app.schemas.prescription_schema import PrescriptionCreate, PrescriptionOut
from app.services.cloudinary_service import fetch_prescription_pdf, upload_prescription_pdf
from app.services.prescription_pdf import generate_prescription_pdf
from app.services.prescription_rag import index_prescription


def _doctor_name(doctor: Dict[str, Any]) -> str:
    return f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()


def _person_name(person: Dict[str, Any]) -> str:
    return f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()


async def _resolve_hospital(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Hospital for a stored prescription; older records resolve it through the appointment."""
    hospital_id = doc.get("hospital_id")
    if not hospital_id:
        appointment = await appointment_crud.get_appointment_by_id(doc.get("appointment_id", ""))
        hospital_id = (appointment or {}).get("hospital_id")
    if not hospital_id:
        return None
    return await hospital_crud.get_hospital_by_id(hospital_id)


async def _to_out(doc: Dict[str, Any]) -> PrescriptionOut:
    doctor = await user_crud.get_user_by_id(doc["doctor_id"])
    patient = await user_crud.get_user_by_id(doc["patient_id"])
    hospital = await _resolve_hospital(doc)
    return PrescriptionOut(**serialize_prescription(
        doc, doctor_name=_doctor_name(doctor or {}),
        patient_name=_person_name(patient or {}) or None, hospital=hospital,
    ))


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
    hospital = await hospital_crud.get_hospital_by_id(appointment.get("hospital_id") or "")
    if not hospital:
        raise HTTPException(status_code=404, detail="The hospital for this appointment was not found.")
    # Ownership always comes from the appointment, never from the request body.
    document = prescription_document(patient_id=appointment["patient_id"], doctor_id=str(current_user["_id"]), hospital_id=str(hospital["_id"]), appointment_id=payload.appointment_id, diagnosis=payload.diagnosis, medicines=[m.model_dump() for m in payload.medicines], general_instructions=payload.general_instructions)
    try:
        # Insert first so the unique appointment index rejects a duplicate before any PDF is written.
        created = await prescription_crud.create_prescription(document)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A prescription already exists for this appointment.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to create prescription.") from exc
    try:
        pdf = generate_prescription_pdf(created, appointment, current_user, patient, hospital)
        url, public_id = upload_prescription_pdf(pdf, str(created["_id"]))
        await prescription_crud.set_pdf(created["_id"], url, public_id)
        created["pdf_url"], created["cloudinary_public_id"] = url, public_id
    except Exception as exc:
        # A prescription without its PDF is unusable, so release the appointment for a retry.
        await prescription_crud.delete_prescription(created["_id"])
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail="Prescription PDF storage is temporarily unavailable.") from exc
        raise HTTPException(status_code=500, detail="Unable to create prescription.") from exc
    try:
        await index_prescription(created, _doctor_name(current_user))
    except Exception:
        # Retrieval index is derived data; source-of-truth prescription remains valid.
        pass
    return PrescriptionOut(**serialize_prescription(created, doctor_name=_doctor_name(current_user), patient_name=_person_name(patient), hospital=hospital))


def _authorize(doc: Dict[str, Any], current_user: Dict[str, Any]) -> None:
    user_id, role = str(current_user["_id"]), current_user.get("role")
    if role in ("customer", "patient"):
        if doc["patient_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not have access to this prescription.")
        return
    if role == "doctor":
        if doc["doctor_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not have access to this prescription.")
        return
    if role not in ("hospital_manager", "super_admin"):
        raise HTTPException(status_code=403, detail="You do not have access to this prescription.")


async def get_one(prescription_id: str, current_user: Dict[str, Any]) -> PrescriptionOut:
    doc = await prescription_crud.get_by_id(prescription_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Prescription not found.")
    _authorize(doc, current_user)
    return await _to_out(doc)


async def mine(current_user: Dict[str, Any]) -> List[PrescriptionOut]:
    if current_user.get("role") not in ("customer", "patient"):
        raise HTTPException(status_code=403, detail="Only patients can list their prescriptions.")
    docs = await prescription_crud.get_for_patient(str(current_user["_id"]))
    return [await _to_out(doc) for doc in docs]


async def by_doctor(current_user: Dict[str, Any]) -> List[PrescriptionOut]:
    if current_user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can list prescriptions they issued.")
    docs = await prescription_crud.get_for_doctor(str(current_user["_id"]))
    return [await _to_out(doc) for doc in docs]


def _download_filename(patient: Dict[str, Any], doc: Dict[str, Any]) -> str:
    name = "".join(ch for ch in _person_name(patient).replace(" ", "_") if ch.isalnum() or ch == "_") or "Patient"
    created = doc.get("created_at")
    date = created.date().isoformat() if created else "prescription"
    return f"CityCare_Prescription_{name}_{date}.pdf"


async def download(prescription_id: str, current_user: Dict[str, Any]) -> Response:
    doc = await prescription_crud.get_by_id(prescription_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Prescription not found.")
    _authorize(doc, current_user)
    pdf_url = doc.get("pdf_url")
    if not pdf_url:
        raise HTTPException(status_code=404, detail="This prescription has no stored PDF.")
    try:
        pdf_bytes = await fetch_prescription_pdf(pdf_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Prescription PDF storage is temporarily unavailable.") from exc
    patient = await user_crud.get_user_by_id(doc["patient_id"]) or {}
    filename = _download_filename(patient, doc)
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
