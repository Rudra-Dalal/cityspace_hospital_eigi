"""Authorization and workflow coverage for prescription endpoints."""
import pytest
from unittest.mock import patch
from tests.conftest import auth_header, login, signup_patient, today_iso

def booking_body():
    return {"date": today_iso(), "slot": "10:00", "reason": "Persistent fever and body pain", "temperature": 99.0, "symptoms": ["fever"]}

async def make_accepted_appointment(client):
    await signup_patient(client, "prescription@example.com")
    patient = await login(client, "prescription@example.com", "Patient@123")
    booked = await client.post("/appointments", json=booking_body(), headers=auth_header(patient["access_token"]))
    doctor = await login(client, "doctor@citycare.clinic", "Doctor@123")
    accepted = await client.patch(f"/appointments/{booked.json()['id']}/accept", headers=auth_header(doctor["access_token"]))
    return patient, doctor, booked.json(), accepted

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
    payload = {"appointment_id": appointment["id"], "diagnosis": "Viral fever", "medicines": [{"name": "Paracetamol", "dosage": "500 mg", "frequency": "Twice daily", "duration": "5 days", "instructions": "After food"}], "general_instructions": "Rest and drink fluids."}
    with patch("app.controllers.prescription_controller.upload_prescription_pdf", return_value=("https://example.test/prescription.pdf", "citycare/prescriptions/x")):
        created = await client.post("/prescriptions", json=payload, headers=auth_header(doctor["access_token"]))
    assert created.status_code == 201, created.text
    assert created.json()["pdf_url"].startswith("https://")
    mine = await client.get("/prescriptions/my", headers=auth_header(patient["access_token"]))
    assert mine.status_code == 200 and len(mine.json()) == 1
    await signup_patient(client, "otherprescription@example.com")
    other = await login(client, "otherprescription@example.com", "Patient@123")
    forbidden = await client.get(f"/prescriptions/{created.json()['id']}", headers=auth_header(other["access_token"]))
    assert forbidden.status_code == 403
