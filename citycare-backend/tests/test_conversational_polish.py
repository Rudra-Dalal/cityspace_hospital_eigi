"""Comprehensive test suite for the final conversational UX polish:
- Natural chat first, buttons second
- Symptom-first intake without buttons
- Non-diagnostic department exploration
- Open-ended doctor query handling without dumping doctors
- Sentence-level relative date & time preference extraction
- Contextual doctor & slot resolution (ordinals, surnames, natural times)
- Context switching (doctor switch, date switch)
- Clean cancellation without clutter
- Conversational registration & pending booking preservation
- Strict prescription security for unverified users
- Full end-to-end natural conversational booking journey
"""

import asyncio
from datetime import date as date_cls, datetime, timezone, timedelta
from typing import Any, Dict, List
import pytest
import pytest_asyncio

from app.core.database import connect_to_mongo, ensure_indexes, get_database
from app.controllers.auth_controller import seed_doctor_if_missing
from app.core.migrate import run_migrations
from app.cruds import appointment_crud, hospital_crud, user_crud
from app.models.hospital_model import hospital_document
from app.models.user_model import UserRole, user_document
from app.services.patient_discovery_service import get_current_date_in_tz
from telegram_gateway.adapter import FakeTelegramAdapter
from telegram_gateway.assistant import (
    parse_relative_date,
    parse_time_preference,
    resolve_doctor_reference,
    resolve_slot_reference,
)
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.models import TelegramFlowType, get_session_key
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


async def create_doctor(
    hospital_id: str,
    first_name: str = "Rajesh",
    last_name: str = "Sharma",
    specialization: str = "Dermatology",
    available_days: List[str] = None,
    valid_slots: List[str] = None,
) -> Dict[str, Any]:
    """Helper to create test doctor user."""
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    doc = await user_crud.create_user(
        user_document(
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}.{last_name.lower()}@citycare.clinic",
            mobile="+919876543000",
            password_hash="dummy_hash",
            role=UserRole.DOCTOR,
            is_active=True,
            hospital_id=hospital_id,
            specialization=specialization,
            qualification="MD, FAAD",
            available_days=available_days or all_days,
            valid_slots=valid_slots or ["10:00 AM", "10:30 AM", "11:00 AM", "02:00 PM", "02:30 PM"],
        )
    )
    return doc


async def setup_hospital_and_dermatologists():
    """Create hospital and two dermatologists."""
    hosp = await hospital_crud.create_hospital(
        hospital_document(
            name="CityCare Central Hospital",
            city="Delhi",
            address="10 Medical Center Way",
            state="Delhi",
            contact_phone="+911122334455",
            contact_email="central@citycare.clinic",
            facilities=["Dermatology Clinic"],
            services=["Consultation"],
            status="active",
        )
    )
    hosp_id = str(hosp["_id"])
    doc1 = await create_doctor(hospital_id=hosp_id, first_name="Rajesh", last_name="Sharma", specialization="Dermatology")
    doc2 = await create_doctor(hospital_id=hosp_id, first_name="Anita", last_name="Mehta", specialization="Dermatology")
    return hosp, doc1, doc2


# ============================================================================
# 1. Greeting & Symptom Intake
# ============================================================================

@pytest.mark.asyncio
async def test_greeting_natural_text():
    """1. Greeting produces friendly text without 'Please select an option below:'."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 101, "type": "private"},
            "from": {"id": 101, "first_name": "Kavita"},
            "text": "Hi",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "Please select an option below:" not in text
    assert "CityCare" in text


@pytest.mark.asyncio
async def test_symptom_intake_request():
    """2. 'Can I tell you my symptoms first?' -> awaiting_symptoms=True, NO KEYBOARD."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 2,
        "message": {
            "message_id": 2,
            "chat": {"id": 102, "type": "private"},
            "from": {"id": 102, "first_name": "Rohan"},
            "text": "Can I tell you my symptoms first?",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "bothering you" in text.lower() or "symptoms" in text.lower()
    assert fake_adapter.last_message.get("reply_markup") is None

    session = await SessionManager.get_session(get_session_key(chat_id=102))
    assert session.flow_data.get("awaiting_symptoms") is True


@pytest.mark.asyncio
async def test_symptom_mapping_no_diagnosis():
    """3. Symptoms mapped to department with non-diagnosis disclaimer and no large keyboard."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 3,
        "message": {
            "message_id": 3,
            "chat": {"id": 103, "type": "private"},
            "from": {"id": 103, "first_name": "Ananya"},
            "text": "I've had a red itchy rash on my arm for three days.",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "dermatology" in text.lower()
    assert "diagnos" in text.lower()
    # At most 1 action button, not a giant keyboard
    markup = fake_adapter.last_message.get("reply_markup")
    if markup:
        assert len(markup.get("inline_keyboard", [])) <= 1


@pytest.mark.asyncio
async def test_open_ended_doctor_request():
    """4. 'I need a doctor' -> asks what help is needed, NO KEYBOARD, no dumping doctors."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    await setup_hospital_and_dermatologists()

    await router.process_update({
        "update_id": 4,
        "message": {
            "message_id": 4,
            "chat": {"id": 104, "type": "private"},
            "from": {"id": 104, "first_name": "Vikram"},
            "text": "I need a doctor",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "what would you like help with" in text.lower() or "bothering you" in text.lower()
    assert fake_adapter.last_message.get("reply_markup") is None


# ============================================================================
# 2. Parsers & Resolvers
# ============================================================================

def test_relative_date_parsing_sentence():
    """5. 'Yes, tomorrow morning.' parses relative date and time preference."""
    tomorrow = (get_current_date_in_tz() + timedelta(days=1)).isoformat()
    parsed_date = parse_relative_date("Yes, tomorrow morning.")
    assert parsed_date == tomorrow

    time_pref = parse_time_preference("Yes, tomorrow morning.")
    assert time_pref == "morning"

    time_pref_pm = parse_time_preference("tomorrow afternoon at 2")
    assert time_pref_pm == "afternoon"


def test_ordinal_doctor_reference_resolvers():
    """7 & 8 & 9. Contextual doctor reference resolution (first, second, surname)."""
    presented_doctors = [
        {"id": "doc1", "name": "Dr. Rajesh Sharma", "last_name": "Sharma", "specialization": "Dermatology"},
        {"id": "doc2", "name": "Dr. Anita Mehta", "last_name": "Mehta", "specialization": "Dermatology"},
    ]

    first_doc = resolve_doctor_reference("the first one", presented_doctors)
    assert first_doc is not None
    assert first_doc["id"] == "doc1"

    second_doc = resolve_doctor_reference("the second doctor", presented_doctors)
    assert second_doc is not None
    assert second_doc["id"] == "doc2"

    surname_doc = resolve_doctor_reference("Sharma", presented_doctors)
    assert surname_doc is not None
    assert surname_doc["id"] == "doc1"

    mehta_doc = resolve_doctor_reference("Dr Mehta", presented_doctors)
    assert mehta_doc is not None
    assert mehta_doc["id"] == "doc2"


def test_slot_reference_resolvers():
    """10 & 11. Contextual slot reference resolution (ordinals, time preference, direct time)."""
    presented_slots = ["10:00 AM", "10:30 AM", "11:00 AM", "02:00 PM", "03:00 PM"]

    s1 = resolve_slot_reference("the first slot", presented_slots)
    assert s1 == "10:00 AM"

    s2 = resolve_slot_reference("the second one", presented_slots)
    assert s2 == "10:30 AM"

    s_time = resolve_slot_reference("10:30", presented_slots)
    assert s_time == "10:30 AM"

    s_morn = resolve_slot_reference("the morning slot", presented_slots)
    assert s_morn == "10:00 AM"


# ============================================================================
# 3. Doctor Presentation & Context Retention
# ============================================================================

@pytest.mark.asyncio
async def test_doctor_presentation_stores_context():
    """6. Presenting doctors populates flow_data['presented_doctors']."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    await router.process_update({
        "update_id": 6,
        "message": {
            "message_id": 6,
            "chat": {"id": 106, "type": "private"},
            "from": {"id": 106, "first_name": "Sneha"},
            "text": "Find dermatologists tomorrow morning",
        },
    })

    assert fake_adapter.last_message is not None
    session = await SessionManager.get_session(get_session_key(chat_id=106))
    assert "presented_doctors" in session.flow_data
    assert len(session.flow_data["presented_doctors"]) >= 2
    assert session.flow_data["presented_doctors"][0]["last_name"] in ("Sharma", "Mehta")


# ============================================================================
# 4. Reason Collection & Summary Card
# ============================================================================

@pytest.mark.asyncio
async def test_reason_collection_no_keyboard():
    """12. Asking for consultation reason notes has NO KEYBOARD."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    # Preload session at select_slot
    tomorrow = (get_current_date_in_tz() + timedelta(days=1)).isoformat()
    session = await SessionManager.get_or_create_session(telegram_user_id=112, chat_id=112)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_slot",
        flow_data={
            "doctor_id": str(doc1["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "specialization": "Dermatology",
            "date": tomorrow,
            "presented_slots": ["10:00 AM", "10:30 AM"],
        },
    )

    await router.process_update({
        "update_id": 112,
        "message": {
            "message_id": 112,
            "chat": {"id": 112, "type": "private"},
            "from": {"id": 112, "first_name": "Tarun"},
            "text": "10:30",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "symptom" in text.lower() or "reason" in text.lower()
    assert fake_adapter.last_message.get("reply_markup") is None


@pytest.mark.asyncio
async def test_booking_summary_card():
    """13. Summary card displays Doctor, Department, Hospital, Date, Time, Reason."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    # Patient registered & linked
    patient = await user_crud.create_user(
        user_document(
            first_name="Pooja",
            last_name="Bansal",
            email="pooja.bansal@example.com",
            mobile="+919876543113",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    p_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=113, telegram_chat_id=113, patient_id=p_id)

    tomorrow = (get_current_date_in_tz() + timedelta(days=1)).isoformat()
    session = await SessionManager.get_or_create_session(telegram_user_id=113, chat_id=113, patient_id=p_id)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="enter_reason",
        flow_data={
            "doctor_id": str(doc1["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "specialization": "Dermatology",
            "date": tomorrow,
            "slot": "10:30 AM",
        },
    )

    await router.process_update({
        "update_id": 113,
        "message": {
            "message_id": 113,
            "chat": {"id": 113, "type": "private"},
            "from": {"id": 113, "first_name": "Pooja"},
            "text": "The rash has been getting worse over three days.",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "Rajesh Sharma" in text
    assert "10:30 AM" in text
    assert "rash" in text.lower()
    assert fake_adapter.last_message.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_text_booking_confirmation():
    """14. Natural text 'Book it' or 'Yes, book it' confirms booking."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    patient = await user_crud.create_user(
        user_document(
            first_name="Sunil",
            last_name="Kumar",
            email="sunil.kumar@example.com",
            mobile="+919876543114",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    p_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=114, telegram_chat_id=114, patient_id=p_id)

    tomorrow = (get_current_date_in_tz() + timedelta(days=1)).isoformat()
    session = await SessionManager.get_or_create_session(telegram_user_id=114, chat_id=114, patient_id=p_id)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="confirm_booking",
        flow_data={
            "doctor_id": str(doc1["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "specialization": "Dermatology",
            "date": tomorrow,
            "slot": "10:30 AM",
            "reason": "Skin consultation",
        },
    )

    await router.process_update({
        "update_id": 114,
        "message": {
            "message_id": 114,
            "chat": {"id": 114, "type": "private"},
            "from": {"id": 114, "first_name": "Sunil"},
            "text": "Yes, book it.",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "Confirmed" in text or "booked with" in text.lower()


# ============================================================================
# 5. Context Switching & Cancellation
# ============================================================================

@pytest.mark.asyncio
async def test_context_switch_doctor():
    """15. 'Actually, someone else' preserves spec/date, clears doctor/slot, shows others."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    tomorrow = (get_current_date_in_tz() + timedelta(days=1)).isoformat()
    session = await SessionManager.get_or_create_session(telegram_user_id=115, chat_id=115)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_slot",
        flow_data={
            "doctor_id": str(doc1["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "specialization": "Dermatology",
            "date": tomorrow,
        },
    )

    await router.process_update({
        "update_id": 115,
        "message": {
            "message_id": 115,
            "chat": {"id": 115, "type": "private"},
            "from": {"id": 115, "first_name": "Neelam"},
            "text": "Actually, someone else",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "another doctor" in text.lower() or "prefer" in text.lower()

    updated = await SessionManager.get_session(get_session_key(chat_id=115))
    assert "doctor_id" not in updated.flow_data
    assert updated.flow_data.get("specialization") == "Dermatology"


@pytest.mark.asyncio
async def test_context_switch_date():
    """16. 'Actually Friday' preserves doctor, updates date, checks availability."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    session = await SessionManager.get_or_create_session(telegram_user_id=116, chat_id=116)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_slot",
        flow_data={
            "doctor_id": str(doc1["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "specialization": "Dermatology",
            "date": "2026-08-28",
        },
    )

    await router.process_update({
        "update_id": 116,
        "message": {
            "message_id": 116,
            "chat": {"id": 116, "type": "private"},
            "from": {"id": 116, "first_name": "Manish"},
            "text": "Actually Friday",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "Dr. Rajesh Sharma" in text or "slot" in text.lower()


@pytest.mark.asyncio
async def test_cancellation_natural():
    """17. 'Cancel that' / 'Never mind' clears flow, gives polite text, NO KEYBOARD."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    session = await SessionManager.get_or_create_session(telegram_user_id=117, chat_id=117)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_slot",
        flow_data={"doctor_name": "Dr. Sharma"},
    )

    await router.process_update({
        "update_id": 117,
        "message": {
            "message_id": 117,
            "chat": {"id": 117, "type": "private"},
            "from": {"id": 117, "first_name": "Gaurav"},
            "text": "Cancel that",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "cancelled that request" in text.lower() or "cleared" in text.lower()
    assert fake_adapter.last_message.get("reply_markup") is None

    cleared = await SessionManager.get_session(get_session_key(chat_id=117))
    assert cleared.current_flow == TelegramFlowType.IDLE.value


# ============================================================================
# 6. Registration & Pending Booking
# ============================================================================

@pytest.mark.asyncio
async def test_conversational_registration_multi_entity():
    """18. Multi-entity registration extracts name, dob, email; asks only missing mobile."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 118,
        "message": {
            "message_id": 118,
            "chat": {"id": 118, "type": "private"},
            "from": {"id": 118, "first_name": "Siddharth"},
            "text": "Register me: Siddharth Roy, 14/07/1995, siddharth.roy@example.com",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "mobile" in text.lower() or "phone" in text.lower()

    session = await SessionManager.get_session(get_session_key(chat_id=118))
    assert session.flow_data.get("first_name") == "Siddharth"
    assert session.flow_data.get("last_name") == "Roy"
    assert session.flow_data.get("email") == "siddharth.roy@example.com"


@pytest.mark.asyncio
async def test_pending_booking_restored():
    """19. Unregistered patient's booking context is saved in pending_booking and restored after registration."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    tomorrow = (get_current_date_in_tz() + timedelta(days=1)).isoformat()
    session = await SessionManager.get_or_create_session(telegram_user_id=119, chat_id=119)
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="confirm_booking",
        flow_data={
            "doctor_id": str(doc1["_id"]),
            "doctor_name": "Dr. Rajesh Sharma",
            "hospital_id": str(hosp["_id"]),
            "hospital_name": hosp["name"],
            "specialization": "Dermatology",
            "date": tomorrow,
            "slot": "10:30 AM",
            "reason": "Skin rash",
        },
    )

    # User says "Yes" without being registered
    await router.process_update({
        "update_id": 119,
        "message": {
            "message_id": 119,
            "chat": {"id": 119, "type": "private"},
            "from": {"id": 119, "first_name": "Dev"},
            "text": "Yes, book it",
        },
    })

    updated = await SessionManager.get_session(get_session_key(chat_id=119))
    assert updated.current_flow == TelegramFlowType.REGISTRATION.value
    assert "pending_booking" in updated.flow_data
    assert updated.flow_data["pending_booking"]["slot"] == "10:30 AM"


@pytest.mark.asyncio
async def test_unverified_prescription_blocked():
    """20. Unverified user asking for prescriptions is safely blocked."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 120,
        "message": {
            "message_id": 120,
            "chat": {"id": 120, "type": "private"},
            "from": {"id": 120, "first_name": "Stranger"},
            "text": "What medicines did my doctor prescribe?",
        },
    })

    assert fake_adapter.last_message is not None
    text = fake_adapter.last_message["text"]
    assert "link" in text.lower() or "register" in text.lower() or "verified" in text.lower()


# ============================================================================
# 7. Complete Full Conversational Journey (Zero Buttons)
# ============================================================================

@pytest.mark.asyncio
async def test_full_conversational_journey():
    """21. Complete end-to-end conversational booking dialogue without pressing any buttons:
    Turn 1: 'Hi'
    Turn 2: 'Can I tell you my symptoms first?'
    Turn 3: "I've had a red itchy rash on my arm for three days."
    Turn 4: 'Yes, tomorrow morning.'
    Turn 5: 'Sharma.'
    Turn 6: 'The first slot.'
    Turn 7: 'The rash has been getting worse.'
    Turn 8: 'Yes, book it.'
    """
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    hosp, doc1, doc2 = await setup_hospital_and_dermatologists()

    # Pre-register patient so final confirmation completes
    patient = await user_crud.create_user(
        user_document(
            first_name="Rudra",
            last_name="Dalal",
            email="rudra.dalal@example.com",
            mobile="+919876543299",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    p_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=999, telegram_chat_id=999, patient_id=p_id)

    # Turn 1: Hi
    await router.process_update({
        "update_id": 1001,
        "message": {"message_id": 1001, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "Hi"},
    })
    assert "CityCare" in fake_adapter.last_message["text"]

    # Turn 2: Can I tell you my symptoms first?
    await router.process_update({
        "update_id": 1002,
        "message": {"message_id": 1002, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "Can I tell you my symptoms first?"},
    })
    assert "bothering you" in fake_adapter.last_message["text"].lower()

    # Turn 3: Describe symptoms
    await router.process_update({
        "update_id": 1003,
        "message": {"message_id": 1003, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "I've had a red itchy rash on my arm for three days."},
    })
    assert "dermatology" in fake_adapter.last_message["text"].lower()

    # Turn 4: Yes, tomorrow morning.
    await router.process_update({
        "update_id": 1004,
        "message": {"message_id": 1004, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "Yes, tomorrow morning."},
    })
    assert "Sharma" in fake_adapter.last_message["text"] or "Mehta" in fake_adapter.last_message["text"]

    # Turn 5: Sharma.
    await router.process_update({
        "update_id": 1005,
        "message": {"message_id": 1005, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "Sharma."},
    })
    assert "slot" in fake_adapter.last_message["text"].lower()

    # Turn 6: The first slot.
    await router.process_update({
        "update_id": 1006,
        "message": {"message_id": 1006, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "The first slot."},
    })
    assert "symptom" in fake_adapter.last_message["text"].lower() or "reason" in fake_adapter.last_message["text"].lower()

    # Turn 7: The rash has been getting worse.
    await router.process_update({
        "update_id": 1007,
        "message": {"message_id": 1007, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "The rash has been getting worse."},
    })
    assert "book this appointment" in fake_adapter.last_message["text"].lower() or "summary" in fake_adapter.last_message["text"].lower()

    # Turn 8: Yes, book it.
    await router.process_update({
        "update_id": 1008,
        "message": {"message_id": 1008, "chat": {"id": 999, "type": "private"}, "from": {"id": 999, "first_name": "Rudra"}, "text": "Yes, book it."},
    })
    assert "confirmed" in fake_adapter.last_message["text"].lower() or "booked with" in fake_adapter.last_message["text"].lower()

    # Verify appointment in database
    db = get_database()
    appt = await db.appointments.find_one({"patient_id": p_id})
    assert appt is not None
    assert appt["doctor_id"] == str(doc1["_id"])
    assert appt["status"] in ("booked", "confirmed")
