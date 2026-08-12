"""Authorization and workflow coverage for prescription endpoints."""
import pytest
from unittest.mock import AsyncMock, patch
from tests.conftest import auth_header, login, signup_patient, today_iso

FAKE_PDF = b"%PDF-1.4 fake prescription bytes"

def booking_body(slot: str = "10:00"):
    return {"date": today_iso(), "slot": slot, "reason": "Persistent fever and body pain", "temperature": 99.0, "symptoms": ["fever"]}

def prescription_body(appointment_id: str):
    return {"appointment_id": appointment_id, "diagnosis": "Viral fever",
            "medicines": [{"name": "Paracetamol", "dosage": "500 mg", "frequency": "Twice daily", "duration": "5 days", "instructions": "After food"}],
            "general_instructions": "Rest and drink fluids."}

def upload_patch():
    return patch("app.controllers.prescription_controller.upload_prescription_pdf", return_value=("https://example.test/prescription.pdf", "citycare/prescriptions/x"))

def fetch_patch():
    return patch("app.controllers.prescription_controller.fetch_prescription_pdf", new=AsyncMock(return_value=FAKE_PDF))

async def make_accepted_appointment(client, email: str = "prescription@example.com", slot: str = "10:00"):
    await signup_patient(client, email)
    patient = await login(client, email, "Patient@123")
    booked = await client.post("/appointments", json=booking_body(slot), headers=auth_header(patient["access_token"]))
    doctor = await login(client, "doctor@citycare.clinic", "Doctor@123")
    accepted = await client.patch(f"/appointments/{booked.json()['id']}/accept", headers=auth_header(doctor["access_token"]))
    return patient, doctor, booked.json(), accepted

async def create_second_doctor(client, email: str = "second.doctor@citycare.clinic"):
    admin = await login(client, "admin@citycare.clinic", "Admin@123")
    hospitals = await client.get("/admin/hospitals", headers=auth_header(admin["access_token"]))
    payload = {"first_name": "Second", "last_name": "Doctor", "email": email, "mobile": "+919876500011",
               "password": "Doctor@1234", "hospital_id": hospitals.json()[0]["id"]}
    created = await client.post("/admin/users/doctor", json=payload, headers=auth_header(admin["access_token"]))
    assert created.status_code == 201, created.text
    return await login(client, email, "Doctor@1234")

@pytest.mark.asyncio
async def test_doctor_accepts_only_assigned_appointment(client):
    patient, doctor, appointment, accepted = await make_accepted_appointment(client)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    rejected = await client.patch(f"/appointments/{appointment['id']}/accept", headers=auth_header(patient["access_token"]))
    assert rejected.status_code == 403

@pytest.mark.asyncio
async def test_prescription_creation_and_patient_isolation(client):
    patient, doctor, appointment, _ = await make_accepted_appointment(client)
    with upload_patch():
        created = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(doctor["access_token"]))
    assert created.status_code == 201, created.text
    assert created.json()["pdf_url"].startswith("https://")
    mine = await client.get("/prescriptions/my", headers=auth_header(patient["access_token"]))
    assert mine.status_code == 200 and len(mine.json()) == 1
    await signup_patient(client, "otherprescription@example.com")
    other = await login(client, "otherprescription@example.com", "Patient@123")
    forbidden = await client.get(f"/prescriptions/{created.json()['id']}", headers=auth_header(other["access_token"]))
    assert forbidden.status_code == 403

@pytest.mark.asyncio
async def test_ownership_is_derived_from_the_appointment(client):
    patient, doctor, appointment, _ = await make_accepted_appointment(client)
    body = prescription_body(appointment["id"])
    # Ownership fields sent by a client must be ignored entirely.
    body.update({"patient_id": "spoofed", "doctor_id": "spoofed", "hospital_id": "spoofed"})
    with upload_patch():
        created = await client.post("/prescriptions", json=body, headers=auth_header(doctor["access_token"]))
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["patient_id"] == patient["user"]["id"]
    assert data["doctor_id"] == doctor["user"]["id"]
    assert data["hospital_id"] == appointment["hospital_id"]
    assert data["hospital"]["name"] and data["hospital"]["id"] == appointment["hospital_id"]

@pytest.mark.asyncio
async def test_patient_cannot_create_prescription(client):
    patient, _, appointment, _ = await make_accepted_appointment(client)
    response = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(patient["access_token"]))
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_doctor_cannot_prescribe_for_another_doctors_appointment(client):
    _, _, appointment, _ = await make_accepted_appointment(client)
    other_doctor = await create_second_doctor(client)
    response = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(other_doctor["access_token"]))
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_prescription_requires_accepted_appointment(client):
    await signup_patient(client, "notaccepted@example.com")
    patient = await login(client, "notaccepted@example.com", "Patient@123")
    booked = await client.post("/appointments", json=booking_body("11:00"), headers=auth_header(patient["access_token"]))
    doctor = await login(client, "doctor@citycare.clinic", "Doctor@123")
    response = await client.post("/prescriptions", json=prescription_body(booked.json()["id"]), headers=auth_header(doctor["access_token"]))
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_duplicate_prescription_returns_conflict(client):
    _, doctor, appointment, _ = await make_accepted_appointment(client)
    with upload_patch():
        first = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(doctor["access_token"]))
        second = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(doctor["access_token"]))
    assert first.status_code == 201
    assert second.status_code == 409

@pytest.mark.asyncio
async def test_doctor_listing_returns_only_own_prescriptions(client):
    _, doctor, appointment, _ = await make_accepted_appointment(client)
    with upload_patch():
        await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(doctor["access_token"]))
    listed = await client.get("/prescriptions/doctor", headers=auth_header(doctor["access_token"]))
    assert listed.status_code == 200 and len(listed.json()) == 1
    assert listed.json()[0]["patient_name"]
    other_doctor = await create_second_doctor(client)
    empty = await client.get("/prescriptions/doctor", headers=auth_header(other_doctor["access_token"]))
    assert empty.status_code == 200 and empty.json() == []

@pytest.mark.asyncio
async def test_download_authorization(client):
    patient, doctor, appointment, _ = await make_accepted_appointment(client)
    with upload_patch():
        created = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(doctor["access_token"]))
    prescription_id = created.json()["id"]

    with fetch_patch():
        as_patient = await client.get(f"/prescriptions/{prescription_id}/download", headers=auth_header(patient["access_token"]))
        as_doctor = await client.get(f"/prescriptions/{prescription_id}/download", headers=auth_header(doctor["access_token"]))
    assert as_patient.status_code == 200 and as_patient.content == FAKE_PDF
    assert as_patient.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"CityCare_Prescription_" in as_patient.headers["content-disposition"]
    assert as_doctor.status_code == 200

    await signup_patient(client, "otherdownload@example.com")
    other_patient = await login(client, "otherdownload@example.com", "Patient@123")
    other_doctor = await create_second_doctor(client)
    with fetch_patch():
        patient_denied = await client.get(f"/prescriptions/{prescription_id}/download", headers=auth_header(other_patient["access_token"]))
        doctor_denied = await client.get(f"/prescriptions/{prescription_id}/download", headers=auth_header(other_doctor["access_token"]))
    anonymous = await client.get(f"/prescriptions/{prescription_id}/download")
    assert patient_denied.status_code == 403
    assert doctor_denied.status_code == 403
    assert anonymous.status_code == 401

@pytest.mark.asyncio
async def test_download_without_stored_pdf_returns_clear_error(client):
    from app.core.database import get_database
    from bson import ObjectId
    patient, doctor, appointment, _ = await make_accepted_appointment(client)
    with upload_patch():
        created = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(doctor["access_token"]))
    prescription_id = created.json()["id"]
    await get_database().prescriptions.update_one({"_id": ObjectId(prescription_id)}, {"$set": {"pdf_url": None}})
    response = await client.get(f"/prescriptions/{prescription_id}/download", headers=auth_header(patient["access_token"]))
    assert response.status_code == 404
    assert "PDF" in response.json()["detail"]

@pytest.mark.asyncio
async def test_legacy_prescription_without_hospital_id_still_reads(client):
    from app.core.database import get_database
    from bson import ObjectId
    patient, doctor, appointment, _ = await make_accepted_appointment(client)
    with upload_patch():
        created = await client.post("/prescriptions", json=prescription_body(appointment["id"]), headers=auth_header(doctor["access_token"]))
    await get_database().prescriptions.update_one({"_id": ObjectId(created.json()["id"])}, {"$unset": {"hospital_id": ""}})
    mine = await client.get("/prescriptions/my", headers=auth_header(patient["access_token"]))
    assert mine.status_code == 200
    assert mine.json()[0]["hospital_id"] == appointment["hospital_id"]
    assert mine.json()[0]["hospital"]["name"]
