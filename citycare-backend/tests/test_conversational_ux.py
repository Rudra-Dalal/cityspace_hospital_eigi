"""Comprehensive test suite for natural conversational UX, intent recognition,
multi-turn context, registration, and security in the Telegram Patient Assistant.
"""

import asyncio
from datetime import date as date_cls, datetime, timezone, timedelta
from typing import Any, Dict
import pytest
import pytest_asyncio

from app.core.database import connect_to_mongo, ensure_indexes, get_database
from app.controllers.auth_controller import seed_doctor_if_missing
from app.core.migrate import run_migrations
from app.cruds import appointment_crud, hospital_crud, prescription_crud, user_crud
from app.models.hospital_model import hospital_document
from app.models.prescription_model import prescription_document
from app.models.user_model import UserRole, user_document
from telegram_gateway.adapter import FakeTelegramAdapter
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.models import TelegramFlowType
from telegram_gateway.router import TelegramRouter
from telegram_gateway.session_manager import SessionManager


@pytest_asyncio.fixture(autouse=True)
async def cleanup_telegram_db():
    """Ensure clean test database state before and after each test."""
    await connect_to_mongo()
    await ensure_indexes()
    db = get_database()
    await db.hospitals.delete_many({})
    await db.users.delete_many({})
    await db.appointments.delete_many({})
    await db.prescriptions.delete_many({})
    await db.prescription_vectors.delete_many({})
    await db.telegram_identities.delete_many({})
    await db.telegram_sessions.delete_many({})
    await db.telegram_otp_tokens.delete_many({})
    await db.account_activation_tokens.delete_many({})
    await db.telegram_idempotency.delete_many({})
    await db.telegram_rate_limits.delete_many({})
    await seed_doctor_if_missing()
    await run_migrations()
    yield
    await db.hospitals.delete_many({})
    await db.users.delete_many({})
    await db.appointments.delete_many({})
    await db.prescriptions.delete_many({})
    await db.telegram_identities.delete_many({})
    await db.telegram_sessions.delete_many({})
    await db.telegram_otp_tokens.delete_many({})
    await db.account_activation_tokens.delete_many({})
    await db.telegram_idempotency.delete_many({})
    await db.telegram_rate_limits.delete_many({})


async def create_test_hospital_and_doctor(
    first_name: str = "Rajesh",
    last_name: str = "Sharma",
    specialization: str = "Dermatology",
    valid_slots: list = None,
):
    """Helper to seed hospital and doctor for testing."""
    if valid_slots is None:
        valid_slots = ["10:00 AM", "10:30 AM", "11:00 AM", "02:00 PM"]
    hospital = await hospital_crud.create_hospital(
        hospital_document(
            name="CityCare Central Hospital",
            address="123 Marine Drive",
            city="Mumbai",
            state="Maharashtra",
            contact_phone="+912212345678",
            contact_email="central@citycare.clinic",
            facilities=["Dermatology Clinic", "Pharmacy", "Laboratory"],
            services=["Outpatient", "Consultation"],
            status="active",
        )
    )
    hosp_id = str(hospital["_id"])

    doctor = await user_crud.create_user(
        user_document(
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}.{last_name.lower()}@citycare.clinic",
            mobile="+919876543211",
            password_hash="dummy_hash",
            role=UserRole.DOCTOR,
            hospital_id=hosp_id,
            specialization=specialization,
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            valid_slots=valid_slots,
            is_active=True,
        )
    )
    return hospital, doctor


@pytest.mark.asyncio
async def test_scenario_1_hi_greeting():
    """Scenario 1: Patient says 'Hi' -> Friendly, professional greeting asking how assistant can help."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 101,
        "message": {
            "message_id": 1,
            "chat": {"id": 111, "type": "private"},
            "from": {"id": 111, "first_name": "Aarav"},
            "text": "Hi",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert "CityCare" in msg_text or "Hello" in msg_text
    assert ("help" in msg_text.lower() or "assist" in msg_text.lower())


@pytest.mark.asyncio
async def test_scenario_2_need_a_doctor():
    """Scenario 2: Patient says 'I need a doctor' -> Helpful follow-up asking what symptoms or specialty."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 102,
        "message": {
            "message_id": 2,
            "chat": {"id": 112, "type": "private"},
            "from": {"id": 112, "first_name": "Priya"},
            "text": "I need a doctor",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"].lower()
    assert ("symptom" in msg_text or "department" in msg_text or "specialist" in msg_text or "care" in msg_text)


@pytest.mark.asyncio
async def test_scenario_3_skin_problem_dermatology():
    """Scenario 3: Patient says 'I have a skin problem' -> Dermatology suggestion & date prompt."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    await create_test_hospital_and_doctor(specialization="Dermatology")

    await router.process_update({
        "update_id": 103,
        "message": {
            "message_id": 3,
            "chat": {"id": 113, "type": "private"},
            "from": {"id": 113, "first_name": "Rohan"},
            "text": "I have a skin problem",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert "Dermatology" in msg_text or "dermatologist" in msg_text.lower()


@pytest.mark.asyncio
async def test_scenario_4_dermatologist_tomorrow():
    """Scenario 4: Patient says 'I need a dermatologist tomorrow' -> Specialization and date extracted."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    await create_test_hospital_and_doctor(first_name="Anita", last_name="Deshmukh", specialization="Dermatology")

    await router.process_update({
        "update_id": 104,
        "message": {
            "message_id": 4,
            "chat": {"id": 114, "type": "private"},
            "from": {"id": 114, "first_name": "Kavita"},
            "text": "I need a dermatologist tomorrow",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Anita" in msg_text or "Dermatology" in msg_text or "Deshmukh" in msg_text or "slot" in msg_text.lower())


@pytest.mark.asyncio
async def test_scenario_5_available_cardiologists():
    """Scenario 5: Patient says 'Show me available cardiologists' -> Lists cardiologists & prompts for date."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    await create_test_hospital_and_doctor(first_name="Vikram", last_name="Mehta", specialization="Cardiology")

    await router.process_update({
        "update_id": 105,
        "message": {
            "message_id": 5,
            "chat": {"id": 115, "type": "private"},
            "from": {"id": 115, "first_name": "Sunil"},
            "text": "Show me available cardiologists",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Vikram" in msg_text or "Mehta" in msg_text or "Cardiology" in msg_text)


@pytest.mark.asyncio
async def test_scenario_6_want_dr_sharma():
    """Scenario 6: Patient says 'I want Dr Sharma' -> Matched to Dr. Sharma & availability checked."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    await create_test_hospital_and_doctor(first_name="Rajesh", last_name="Sharma", specialization="Dermatology")

    await router.process_update({
        "update_id": 106,
        "message": {
            "message_id": 6,
            "chat": {"id": 116, "type": "private"},
            "from": {"id": 116, "first_name": "Amit"},
            "text": "I want Dr Sharma",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Sharma" in msg_text or "Rajesh" in msg_text)


@pytest.mark.asyncio
async def test_scenario_7_book_tomorrow_1030():
    """Scenario 7: Patient says 'Book me for tomorrow at 10:30' with doctor in session -> Slot recognized."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc = await create_test_hospital_and_doctor(first_name="Rajesh", last_name="Sharma")

    # Patient registered & linked
    patient = await user_crud.create_user(
        user_document(
            first_name="Amit",
            last_name="Verma",
            email="amit.verma@example.com",
            mobile="+919876543212",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    patient_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=117, telegram_chat_id=117, patient_id=patient_id)

    # Pre-populate session with doctor
    session = await SessionManager.get_or_create_session(
        telegram_user_id=117,
        chat_id=117,
        patient_id=patient_id,
    )
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_slot",
        flow_data={
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "doctor_id": str(doc["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
        },
    )

    await router.process_update({
        "update_id": 107,
        "message": {
            "message_id": 7,
            "chat": {"id": 117, "type": "private"},
            "from": {"id": 117, "first_name": "Amit"},
            "text": "Book me for tomorrow at 10:30",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("10:30" in msg_text or "symptom" in msg_text.lower() or "reason" in msg_text.lower() or "confirm" in msg_text.lower())


@pytest.mark.asyncio
async def test_scenario_8_need_to_register():
    """Scenario 8: Patient says 'I need to register' -> Registration workflow initiated conversationally."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 108,
        "message": {
            "message_id": 8,
            "chat": {"id": 118, "type": "private"},
            "from": {"id": 118, "first_name": "Deepak"},
            "text": "I need to register",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Registration" in msg_text or "name" in msg_text.lower())


@pytest.mark.asyncio
async def test_scenario_9_multi_entity_registration_and_confirmation():
    """Scenario 9: Multi-entity extraction ('My name is Rudra Dalal and my DOB is 12/05/2004')
    Extracts name and DOB, asks only for missing fields, then shows confirmation summary card.
    """
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    # 1. Provide name & DOB together
    await router.process_update({
        "update_id": 1091,
        "message": {
            "message_id": 91,
            "chat": {"id": 119, "type": "private"},
            "from": {"id": 119, "first_name": "Rudra"},
            "text": "My name is Rudra Dalal and my DOB is 12/05/2004",
        },
    })

    assert fake_adapter.last_message is not None
    msg1 = fake_adapter.last_message["text"]
    # Should acknowledge name and ask for email
    assert ("Rudra" in msg1 or "email" in msg1.lower())
    assert "What is your full name" not in msg1

    # 2. Provide email
    await router.process_update({
        "update_id": 1092,
        "message": {
            "message_id": 92,
            "chat": {"id": 119, "type": "private"},
            "from": {"id": 119, "first_name": "Rudra"},
            "text": "rudra.dalal@example.com",
        },
    })

    assert fake_adapter.last_message is not None
    msg2 = fake_adapter.last_message["text"]
    assert ("mobile" in msg2.lower() or "number" in msg2.lower())

    # 3. Provide mobile number
    await router.process_update({
        "update_id": 1093,
        "message": {
            "message_id": 93,
            "chat": {"id": 119, "type": "private"},
            "from": {"id": 119, "first_name": "Rudra"},
            "text": "+919876543210",
        },
    })

    assert fake_adapter.last_message is not None
    msg3 = fake_adapter.last_message["text"]
    # Should display summary card with extracted fields
    assert "Here's what I have" in msg3 or "Name:" in msg3
    assert "Rudra Dalal" in msg3
    assert "rudra" in msg3 and "dalal" in msg3 and "example" in msg3

    # 4. Patient confirms summary card
    await router.process_update({
        "update_id": 1094,
        "message": {
            "message_id": 94,
            "chat": {"id": 119, "type": "private"},
            "from": {"id": 119, "first_name": "Rudra"},
            "text": "Yes, confirm",
        },
    })

    assert fake_adapter.last_message is not None
    msg4 = fake_adapter.last_message["text"]
    assert ("Registration Successful" in msg4 or "Welcome to CityCare" in msg4)

    # Verify patient created and linked in database
    ident, pat = await IdentityManager.resolve_identity(119)
    assert ident is not None
    assert pat is not None
    assert pat["email"] == "rudra.dalal@example.com"


@pytest.mark.asyncio
async def test_scenario_10_show_latest_prescription_verified():
    """Scenario 10: Verified patient says 'Show my latest prescription' -> Displays summary + PDF button."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc = await create_test_hospital_and_doctor()

    patient = await user_crud.create_user(
        user_document(
            first_name="Neha",
            last_name="Kapoor",
            email="neha.kapoor@example.com",
            mobile="+919876543213",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    patient_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=120, telegram_chat_id=120, patient_id=patient_id)

    # Seed prescription
    rx_doc = prescription_document(
        patient_id=patient_id,
        doctor_id=str(doc["_id"]),
        appointment_id="appt_neha_10",
        diagnosis="Eczema / Contact Dermatitis",
        medicines=[
            {
                "name": "Hydrocortisone Cream 1%",
                "dosage": "1 application",
                "frequency": "Twice daily",
                "duration": "7 days",
                "instructions": "Apply thin layer to affected skin",
            }
        ],
        general_instructions="Apply topical ointment twice daily after cleansing. Follow up in one week.",
    )
    rx_doc["pdf_url"] = "https://res.cloudinary.com/citycare/image/upload/v12345/prescriptions/neha.pdf"
    rx_doc["cloudinary_public_id"] = "citycare/prescriptions/neha"
    await prescription_crud.create_prescription(rx_doc)

    await router.process_update({
        "update_id": 110,
        "message": {
            "message_id": 10,
            "chat": {"id": 120, "type": "private"},
            "from": {"id": 120, "first_name": "Neha"},
            "text": "Show my latest prescription",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert "Eczema" in msg_text or "Dermatitis" in msg_text
    assert "Hydrocortisone" in msg_text
    # Verify PDF download button exists in reply markup
    markup = fake_adapter.last_message.get("reply_markup", {})
    keyboard = markup.get("inline_keyboard", [])
    flat_buttons = [btn["text"] for row in keyboard for btn in row]
    assert any("PDF" in b for b in flat_buttons)


@pytest.mark.asyncio
async def test_scenario_11_medicines_prescribed():
    """Scenario 11: Verified patient asks 'What medicines did my doctor prescribe?' -> Shows medicines."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc = await create_test_hospital_and_doctor()

    patient = await user_crud.create_user(
        user_document(
            first_name="Ramesh",
            last_name="Pillai",
            email="ramesh.pillai@example.com",
            mobile="+919876543214",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    patient_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=121, telegram_chat_id=121, patient_id=patient_id)

    rx_doc = prescription_document(
        patient_id=patient_id,
        doctor_id=str(doc["_id"]),
        appointment_id="appt_ramesh_11",
        diagnosis="Allergic Rhinitis",
        medicines=[
            {
                "name": "Cetirizine 10mg",
                "dosage": "1 tablet",
                "frequency": "Once daily at night",
                "duration": "5 days",
                "instructions": "Take after dinner",
            }
        ],
        general_instructions="Rest and drink plenty of fluids.",
    )
    await prescription_crud.create_prescription(rx_doc)

    await router.process_update({
        "update_id": 111,
        "message": {
            "message_id": 11,
            "chat": {"id": 121, "type": "private"},
            "from": {"id": 121, "first_name": "Ramesh"},
            "text": "What medicines did my doctor prescribe?",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert "Cetirizine" in msg_text
    assert "10mg" in msg_text or "Once daily" in msg_text


@pytest.mark.asyncio
async def test_scenario_12_see_appointments():
    """Scenario 12: Verified patient says 'I want to see my appointments' -> Lists appointments with cancel."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc = await create_test_hospital_and_doctor()

    patient = await user_crud.create_user(
        user_document(
            first_name="Divya",
            last_name="Nair",
            email="divya.nair@example.com",
            mobile="+919876543215",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    patient_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=122, telegram_chat_id=122, patient_id=patient_id)

    # Create appointment
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    await appointment_crud.create_appointment({
        "patient_id": patient_id,
        "patient_name": "Divya Nair",
        "doctor_id": str(doc["_id"]),
        "doctor_name": f"Dr. {doc['first_name']} {doc['last_name']}",
        "hospital_id": str(hosp["_id"]),
        "hospital_name": hosp["name"],
        "date": tomorrow,
        "slot": "10:30 AM",
        "reason": "General checkup",
        "status": "booked",
    })

    await router.process_update({
        "update_id": 112,
        "message": {
            "message_id": 12,
            "chat": {"id": 122, "type": "private"},
            "from": {"id": 122, "first_name": "Divya"},
            "text": "I want to see my appointments",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Appointments" in msg_text or "10:30 AM" in msg_text or "Checkup" in msg_text or "Sharma" in msg_text)
    # Check cancel button
    markup = fake_adapter.last_message.get("reply_markup", {})
    keyboard = markup.get("inline_keyboard", [])
    flat_buttons = [btn["text"] for row in keyboard for btn in row]
    assert any("Cancel" in b for b in flat_buttons)


@pytest.mark.asyncio
async def test_scenario_13_different_doctor_context_switch():
    """Scenario 13: Patient says 'Actually, I want a different doctor' mid-booking -> Doctor selection resets."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1 = await create_test_hospital_and_doctor(first_name="Rajesh", last_name="Sharma")

    patient = await user_crud.create_user(
        user_document(
            first_name="Karan",
            last_name="Johar",
            email="karan.johar@example.com",
            mobile="+919876543216",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    patient_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=123, telegram_chat_id=123, patient_id=patient_id)

    session = await SessionManager.get_or_create_session(telegram_user_id=123, chat_id=123, patient_id=patient_id)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_slot",
        flow_data={
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "doctor_id": str(doc1["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
            "specialization": "Dermatology",
        },
    )

    await router.process_update({
        "update_id": 113,
        "message": {
            "message_id": 13,
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 123, "first_name": "Karan"},
            "text": "Actually, I want a different doctor",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("doctor" in msg_text.lower() or "prefer" in msg_text.lower() or "department" in msg_text.lower())

    # Verify session doctor was cleared
    refreshed_session = await SessionManager.get_session(session.session_key)
    assert refreshed_session.flow_data.get("doctor_id") is None


@pytest.mark.asyncio
async def test_scenario_14_changed_my_mind_cancel():
    """Scenario 14: Patient says 'I changed my mind' during booking -> Gracefully cancels active workflow."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    session = await SessionManager.get_or_create_session(telegram_user_id=124, chat_id=124)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="enter_reason",
        flow_data={"doctor_name": "Dr. Sharma"},
    )

    await router.process_update({
        "update_id": 114,
        "message": {
            "message_id": 14,
            "chat": {"id": 124, "type": "private"},
            "from": {"id": 124, "first_name": "Alok"},
            "text": "I changed my mind",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Cancelled" in msg_text or "cancelled" in msg_text.lower() or "cleared" in msg_text.lower())

    # Flow must be cleared
    refreshed_session = await SessionManager.get_session(session.session_key)
    assert refreshed_session.current_flow == TelegramFlowType.IDLE.value


# ============================================================
# Security & Failure Tests
# ============================================================

@pytest.mark.asyncio
async def test_security_unverified_user_cannot_access_prescription():
    """Security 1: Unverified user asks 'Show my prescription' -> Access denied, prompted to link/register."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 201,
        "message": {
            "message_id": 201,
            "chat": {"id": 999, "type": "private"},
            "from": {"id": 999, "first_name": "Stranger"},
            "text": "Show my prescription",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Verification Required" in msg_text or "link" in msg_text.lower() or "register" in msg_text.lower())


@pytest.mark.asyncio
async def test_security_cross_patient_isolation():
    """Security 2: Telegram User A cannot view User B's prescription data."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc = await create_test_hospital_and_doctor()

    # User B has a prescription
    user_b = await user_crud.create_user(
        user_document(
            first_name="User",
            last_name="B",
            email="user.b@example.com",
            mobile="+919876543217",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    b_id = str(user_b["_id"])
    await prescription_crud.create_prescription(
        prescription_document(
            patient_id=b_id,
            doctor_id=str(doc["_id"]),
            appointment_id="appt_secret_b",
            diagnosis="Private Secret Condition",
            medicines=[],
            general_instructions="Confidential notes",
        )
    )

    # User A is linked with different account
    user_a = await user_crud.create_user(
        user_document(
            first_name="User",
            last_name="A",
            email="user.a@example.com",
            mobile="+919876543218",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    a_id = str(user_a["_id"])
    await IdentityManager.link_patient(telegram_user_id=125, telegram_chat_id=125, patient_id=a_id)

    # User A asks for prescriptions
    await router.process_update({
        "update_id": 202,
        "message": {
            "message_id": 202,
            "chat": {"id": 125, "type": "private"},
            "from": {"id": 125, "first_name": "UserA"},
            "text": "Show my latest prescription",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert "Private Secret Condition" not in msg_text
    assert ("no prescriptions" in msg_text.lower() or "do not have" in msg_text.lower())


@pytest.mark.asyncio
async def test_midflow_specialization_switch():
    """Security 3: Patient changes specialization mid-flow ('Actually I need a dentist instead') -> Specialization updated."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    await create_test_hospital_and_doctor(first_name="Sanjay", last_name="Dentist", specialization="Dentistry")

    session = await SessionManager.get_or_create_session(telegram_user_id=126, chat_id=126)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_doctor",
        flow_data={"specialization": "Dermatology"},
    )

    await router.process_update({
        "update_id": 203,
        "message": {
            "message_id": 203,
            "chat": {"id": 126, "type": "private"},
            "from": {"id": 126, "first_name": "Tarun"},
            "text": "Actually I need a dentist instead",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Dentistry" in msg_text or "Dentist" in msg_text or "doctor" in msg_text.lower())


@pytest.mark.asyncio
async def test_incomplete_booking_info_followup():
    """Security 4: Incomplete booking info ('Book appointment') -> Assistant asks intelligent follow-up without error."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 204,
        "message": {
            "message_id": 204,
            "chat": {"id": 127, "type": "private"},
            "from": {"id": 127, "first_name": "Maya"},
            "text": "Book appointment",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("doctor" in msg_text.lower() or "department" in msg_text.lower() or "register" in msg_text.lower())
    assert "error" not in msg_text.lower()
    assert "traceback" not in msg_text.lower()


@pytest.mark.asyncio
async def test_gemini_unavailable_deterministic_fallback(monkeypatch):
    """Security 5: Gemini service unavailable or times out -> Deterministic fallback handles message smoothly."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-api-key-12345")

    class TimeoutModels:
        async def generate_content(self, *args, **kwargs):
            raise asyncio.TimeoutError("Gemini call timed out after 3.5s")

    class FakeAio:
        models = TimeoutModels()

    class FakeGenaiClient:
        aio = FakeAio()

    import google.genai
    monkeypatch.setattr(google.genai, "Client", lambda *args, **kwargs: FakeGenaiClient())

    await router.process_update({
        "update_id": 205,
        "message": {
            "message_id": 205,
            "chat": {"id": 128, "type": "private"},
            "from": {"id": 128, "first_name": "Rani"},
            "text": "I have severe skin rash and itchiness",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert "Dermatology" in msg_text or "dermatologist" in msg_text.lower()


@pytest.mark.asyncio
async def test_gemini_malformed_response_handled_gracefully(monkeypatch):
    """Security 6: Gemini returns malformed response -> Handled gracefully by fallback intent classification."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    class FakeGenaiResponse:
        text = "{ this is invalid json syntax "

    class FakeModels:
        async def generate_content(self, *args, **kwargs):
            return FakeGenaiResponse()

    class FakeAio:
        models = FakeModels()

    class FakeGenaiClient:
        aio = FakeAio()

    import google.genai
    monkeypatch.setattr(google.genai, "Client", lambda *args, **kwargs: FakeGenaiClient())

    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-api-key-12345")

    await router.process_update({
        "update_id": 206,
        "message": {
            "message_id": 206,
            "chat": {"id": 129, "type": "private"},
            "from": {"id": 129, "first_name": "Vijay"},
            "text": "I need to see a cardiologist",
        },
    })

    assert fake_adapter.last_message is not None
    msg_text = fake_adapter.last_message["text"]
    assert ("Cardiology" in msg_text or "cardiologist" in msg_text.lower() or "doctor" in msg_text.lower())


@pytest.mark.asyncio
async def test_unregistered_patient_preserves_booking_context():
    """Section 14: Unregistered user tries to book -> Registration initiated with pending booking resumed."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc = await create_test_hospital_and_doctor(first_name="Pooja", last_name="Bhatia")

    # 1. Unregistered user requests booking
    await router.process_update({
        "update_id": 301,
        "message": {
            "message_id": 301,
            "chat": {"id": 130, "type": "private"},
            "from": {"id": 130, "first_name": "Sameer"},
            "text": "/book",
        },
    })

    assert fake_adapter.last_message is not None
    msg1 = fake_adapter.last_message["text"]
    assert ("don't have a CityCare patient profile" in msg1 or "register" in msg1.lower())

    # 2. Provide registration entities in one go
    await router.process_update({
        "update_id": 302,
        "message": {
            "message_id": 302,
            "chat": {"id": 130, "type": "private"},
            "from": {"id": 130, "first_name": "Sameer"},
            "text": "Sameer Verma, DOB 15/08/1995, email sameer.verma@example.com, mobile +919876543220",
        },
    })

    assert fake_adapter.last_message is not None
    msg2 = fake_adapter.last_message["text"]
    assert "Here's what I have" in msg2 or "Sameer Verma" in msg2

    # 3. Confirm registration
    await router.process_update({
        "update_id": 303,
        "message": {
            "message_id": 303,
            "chat": {"id": 130, "type": "private"},
            "from": {"id": 130, "first_name": "Sameer"},
            "text": "Confirm",
        },
    })

    assert fake_adapter.last_message is not None
    all_sent = [m["text"] for m in fake_adapter.sent_messages]
    assert any("Registration Successful" in t or "Welcome" in t for t in all_sent)
    assert any("complete your appointment booking" in t.lower() or "hospital" in t.lower() for t in all_sent)
