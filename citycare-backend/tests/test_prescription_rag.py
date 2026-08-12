"""PDF generation and patient-isolated prescription retrieval coverage."""

from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from pypdf import PdfReader

from app.services.prescription_pdf import generate_prescription_pdf
from app.services.prescription_rag import index_prescription, retrieve_for_patient


def test_generated_prescription_is_a_valid_pdf():
    prescription = {
        "created_at": datetime.now(timezone.utc),
        "diagnosis": "Seasonal viral fever",
        "medicines": [{
            "name": "Paracetamol", "dosage": "500 mg", "frequency": "Twice daily",
            "duration": "3 days", "instructions": "After food",
        }],
        "general_instructions": "Rest and drink fluids.",
    }
    pdf = generate_prescription_pdf(
        prescription,
        {"date": "2026-08-10", "slot": "10:00"},
        {"first_name": "Meera", "last_name": "Kulkarni"},
        {"first_name": "Patient", "last_name": "One"},
    )

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


def test_generated_prescription_contains_every_field():
    prescription = {
        "created_at": datetime.now(timezone.utc),
        "diagnosis": "Seasonal viral fever",
        "medicines": [
            {"name": "Paracetamol", "dosage": "500 mg", "frequency": "Twice daily",
             "duration": "3 days", "instructions": "After food"},
            {"name": "Azithromycin", "dosage": "250 mg", "frequency": "Once daily",
             "duration": "5 days", "instructions": "Before sleep"},
        ],
        "general_instructions": "Rest and drink fluids.",
    }
    pdf = generate_prescription_pdf(
        prescription,
        {"date": "2026-08-10", "slot": "10:00"},
        {"first_name": "Meera", "last_name": "Kulkarni"},
        {"first_name": "Patient", "last_name": "One"},
        {"name": "CityCare Central Hospital", "address": "12 Ring Road", "city": "Nagpur",
         "state": "Maharashtra", "contact_phone": "+919999999999", "contact_email": "care@citycare.clinic"},
    )
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)

    for expected in ("Patient One", "Dr. Meera Kulkarni", "CityCare Central Hospital", "Nagpur",
                     "2026-08-10", "Seasonal viral fever", "Paracetamol", "Azithromycin",
                     "500 mg", "Twice daily", "3 days", "After food", "Before sleep",
                     "Rest and drink fluids."):
        assert expected in text


@pytest.mark.asyncio
async def test_rag_retrieval_is_scoped_to_the_authenticated_patient(client):
    prescription = {
        "_id": "prescription-a",
        "patient_id": "patient-a",
        "doctor_id": "doctor-a",
        "appointment_id": "appointment-a",
        "created_at": datetime.now(timezone.utc),
        "diagnosis": "Viral fever",
        "medicines": [{
            "name": "Paracetamol", "dosage": "500 mg", "frequency": "Twice daily",
            "duration": "5 days", "instructions": "After food",
        }],
        "general_instructions": "Rest and drink fluids.",
    }
    await index_prescription(prescription, "Dr. Meera Kulkarni")

    own_records = await retrieve_for_patient("patient-a", "What medicine and dosage was prescribed?")
    other_records = await retrieve_for_patient("patient-b", "What medicine and dosage was prescribed?")

    assert len(own_records) == 1
    assert own_records[0]["patient_id"] == "patient-a"
    assert "Paracetamol" in own_records[0]["text"]
    assert other_records == []


@pytest.mark.asyncio
async def test_patient_chat_uses_authenticated_identity_for_retrieval():
    from app.ai.patient_service import run_patient_chat

    with patch("app.ai.patient_service.retrieve_for_patient", new=AsyncMock(return_value=[])) as retrieve:
        reply, sources = await run_patient_chat("What did another patient receive?", {"_id": "patient-a"})

    retrieve.assert_awaited_once_with("patient-a", "What did another patient receive?")
    assert "could not find prescription information" in reply.lower()
    assert sources == []
