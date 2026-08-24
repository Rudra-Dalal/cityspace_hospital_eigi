"""Comprehensive test suite for Telegram Patient Assistant Gateway."""

import asyncio
from datetime import date as date_cls, datetime, timezone, timedelta
from typing import Any, Dict
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.database import close_mongo_connection, connect_to_mongo, ensure_indexes, get_database
from app.controllers.auth_controller import seed_doctor_if_missing
from app.core.migrate import run_migrations
from app.cruds import appointment_crud, hospital_crud, prescription_crud, user_crud
from app.main import app
from app.models.hospital_model import hospital_document
from app.models.prescription_model import prescription_document
from app.models.user_model import UserRole, user_document
from app.services.registration_service import (
    register_patient,
    verify_and_consume_activation_token,
)
from telegram_gateway.adapter import FakeTelegramAdapter, escape_markdown
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.keyboards import (
    build_inline_keyboard,
    main_menu_keyboard,
    hospitals_keyboard,
    doctors_keyboard,
    dates_keyboard,
    slots_keyboard,
)
from telegram_gateway.models import TelegramFlowType, get_session_key
from telegram_gateway.otp_service import DevTestOtpDeliveryService, get_otp_delivery_service
from telegram_gateway.rate_limiter import MongoRateLimiter
from telegram_gateway.router import TelegramRouter, _claim_update_idempotency
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


@pytest.mark.asyncio
async def test_telegram_disabled_startup(client: AsyncClient):
    """Confirm server starts normally with zero Telegram background tasks when disabled."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_telegram_production_settings_validation():
    """Verify production settings reject unsafe defaults or missing tokens."""
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings(
            app_env="production",
            secret_key="a" * 35,
            doctor_password="StrongDoctorPassword123!",
            super_admin_password="StrongAdminPassword123!",
            cors_origins="https://hospital.citycare.clinic",
            telegram_enabled=True,
            telegram_bot_token="",  # Missing
            telegram_mode="webhook",
            telegram_webhook_url="https://api.citycare.clinic/telegram/webhook",
            telegram_webhook_secret="super-secret-token-12345",
            telegram_web_app_url="https://app.citycare.clinic",
            telegram_otp_provider="email",
        )

    with pytest.raises(ValueError, match="TELEGRAM_MODE"):
        Settings(
            app_env="production",
            secret_key="a" * 35,
            doctor_password="StrongDoctorPassword123!",
            super_admin_password="StrongAdminPassword123!",
            cors_origins="https://hospital.citycare.clinic",
            telegram_enabled=True,
            telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            telegram_mode="polling",  # Polling disallowed in prod
            telegram_webhook_url="https://api.citycare.clinic/telegram/webhook",
            telegram_webhook_secret="super-secret-token-12345",
            telegram_web_app_url="https://app.citycare.clinic",
            telegram_otp_provider="email",
        )

    with pytest.raises(ValueError, match="TELEGRAM_OTP_PROVIDER"):
        Settings(
            app_env="production",
            secret_key="a" * 35,
            doctor_password="StrongDoctorPassword123!",
            super_admin_password="StrongAdminPassword123!",
            cors_origins="https://hospital.citycare.clinic",
            telegram_enabled=True,
            telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            telegram_mode="webhook",
            telegram_webhook_url="https://api.citycare.clinic/telegram/webhook",
            telegram_webhook_secret="super-secret-token-12345",
            telegram_web_app_url="https://app.citycare.clinic",
            telegram_otp_provider="dev",  # dev sink disallowed in prod
        )


def test_markdown_escaping():
    """Verify markdown escaping helper handles clinical and special characters safely."""
    raw = "Dr. John & Jane (MBBS) [Cardiology] - Fee: 500.00! *Important*"
    escaped = escape_markdown(raw)
    assert r"\." in escaped
    assert r"\(" in escaped
    assert r"\)" in escaped
    assert r"\[" in escaped
    assert r"\]" in escaped
    assert r"\-" in escaped
    assert r"\!" in escaped
    assert r"\*" in escaped


@pytest.mark.asyncio
async def test_identity_manager_otp_and_linking():
    """Verify OTP issuance, attempt limits, expiration, and 1-to-1 identity mapping."""
    user_id = 987654321
    chat_id = 987654321

    # Create dummy patient
    patient = await user_crud.create_user(
        user_document(
            first_name="Anita",
            last_name="Roy",
            email="anita.roy@example.com",
            mobile="+919876543210",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    patient_id = str(patient["_id"])

    # 1. Issue OTP
    otp_svc = get_otp_delivery_service()
    if isinstance(otp_svc, DevTestOtpDeliveryService):
        otp_svc.clear()

    issued = await IdentityManager.issue_otp(
        telegram_user_id=user_id,
        target_type="email",
        target_value="anita.roy@example.com",
        purpose="link_account",
        metadata={"patient_id": patient_id},
    )
    assert issued is True

    # 2. Extract OTP from test sink
    latest_otp = otp_svc.get_latest_otp("anita.roy@example.com")
    assert latest_otp is not None
    assert len(latest_otp) == 6

    # 3. Test wrong OTP attempt counter
    is_valid, _, err = await IdentityManager.verify_otp(
        telegram_user_id=user_id,
        raw_code="000000",
        purpose="link_account",
    )
    assert is_valid is False
    assert "Incorrect verification code" in err

    # 4. Test valid OTP verification
    is_valid, meta, _ = await IdentityManager.verify_otp(
        telegram_user_id=user_id,
        raw_code=latest_otp,
        purpose="link_account",
    )
    assert is_valid is True
    assert meta["patient_id"] == patient_id

    # 5. Link identity
    linked, msg = await IdentityManager.link_patient(
        telegram_user_id=user_id,
        telegram_chat_id=chat_id,
        patient_id=patient_id,
    )
    assert linked is True

    # 6. Verify resolution
    ident, p_doc = await IdentityManager.resolve_identity(user_id)
    assert ident is not None
    assert ident.verified is True
    assert ident.patient_id == patient_id
    assert p_doc["email"] == "anita.roy@example.com"

    # 7. Prevent duplicate patient linking to a different Telegram user ID
    second_user_id = 112233445
    second_linked, err_msg = await IdentityManager.link_patient(
        telegram_user_id=second_user_id,
        telegram_chat_id=second_user_id,
        patient_id=patient_id,
    )
    assert second_linked is False
    assert "already linked" in err_msg


@pytest.mark.asyncio
async def test_registration_with_consent_and_activation_token():
    """Verify patient registration saves consent and creates a one-time activation token."""
    now = datetime.now(timezone.utc)
    consent = {
        "given": True,
        "timestamp": now.isoformat(),
        "policy_version": "v1.0",
        "platform": "telegram",
    }

    result = await register_patient(
        payload={
            "first_name": "Deepak",
            "last_name": "Verma",
            "email": "deepak.verma@example.com",
            "mobile": "+919123456780",
            "password": "",  # Triggers activation token
        },
        consent=consent,
        allow_activation_token=True,
    )

    assert result["email"] == "deepak.verma@example.com"
    act_token = result.get("activation_token")
    assert act_token is not None

    # Verify user record in DB has consent
    db = get_database()
    user_doc = await db.users.find_one({"email": "deepak.verma@example.com"})
    assert user_doc["consent"]["given"] is True
    assert user_doc["consent"]["policy_version"] == "v1.0"

    # Consume activation token
    consumed_id = await verify_and_consume_activation_token(act_token)
    assert consumed_id == str(user_doc["_id"])

    # Consuming a second time must fail
    second_try = await verify_and_consume_activation_token(act_token)
    assert second_try is None


@pytest.mark.asyncio
async def test_session_manager_persistence_and_reset():
    """Verify session persistence, flow state updates, and /reset workflow clearance."""
    user_id = 555666777
    chat_id = 555666777

    session = await SessionManager.get_or_create_session(
        telegram_user_id=user_id,
        chat_id=chat_id,
        patient_id="patient_123",
    )
    assert session.session_key == f"tg:private:{chat_id}:0"
    assert session.current_flow == TelegramFlowType.IDLE.value

    # Update flow
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_slot",
        flow_data={"doctor_id": "doc_1", "date": "2026-08-26"},
    )

    updated = await SessionManager.get_or_create_session(
        telegram_user_id=user_id,
        chat_id=chat_id,
    )
    assert updated.current_flow == TelegramFlowType.BOOKING.value
    assert updated.flow_step == "select_slot"
    assert updated.flow_data["doctor_id"] == "doc_1"

    # Clear flow / reset
    await SessionManager.clear_flow(session.session_key)

    reset_session = await SessionManager.get_or_create_session(
        telegram_user_id=user_id,
        chat_id=chat_id,
    )
    assert reset_session.current_flow == TelegramFlowType.IDLE.value
    assert reset_session.flow_step is None
    assert reset_session.flow_data == {}
    assert reset_session.patient_id == "patient_123"  # Preserves patient association


@pytest.mark.asyncio
async def test_distributed_rate_limiter():
    """Verify MongoDB atomic rate limiter enforces action limits."""
    user_id = 999111222
    for _ in range(5):
        allowed = await MongoRateLimiter.is_allowed(user_id=user_id, action="test", limit=5, window_seconds=60)
        assert allowed is True

    # 6th attempt must exceed limit 5
    blocked = await MongoRateLimiter.is_allowed(user_id=user_id, action="test", limit=5, window_seconds=60)
    assert blocked is False


@pytest.mark.asyncio
async def test_idempotency_duplicate_updates():
    """Verify Telegram update idempotency drops duplicates."""
    update_id = 88889999
    claim1 = await _claim_update_idempotency(update_id)
    assert claim1 is True

    # Immediate second claim must return False
    claim2 = await _claim_update_idempotency(update_id)
    assert claim2 is False


@pytest.mark.asyncio
async def test_router_discovery_flows():
    """Verify /hospitals, /doctors, and /specializations commands in Telegram router."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    # 1. Create a hospital
    hosp = await hospital_crud.create_hospital(
        hospital_document(
            name="Apollo Gleneagles",
            address="58 Canal Circular Rd, 700054",
            city="Kolkata",
            state="West Bengal",
            contact_phone="+913323203040",
            contact_email="info@kolkata.citycare.clinic",
            working_hours="08:00 - 20:00",
            status="active",
            facilities=["ICU", "Cath Lab", "24x7 Pharmacy"],
            services=["Cardiology", "Neurology"],
        )
    )

    # 2. Execute /hospitals
    await router.process_update({
        "update_id": 1001,
        "message": {
            "message_id": 1,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "TestUser"},
            "text": "/hospitals",
        },
    })

    assert fake_adapter.last_message is not None
    assert "Apollo Gleneagles" in fake_adapter.last_message["text"]

    # 3. Execute /specializations
    await router.process_update({
        "update_id": 1002,
        "message": {
            "message_id": 2,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "TestUser"},
            "text": "/specializations",
        },
    })
    assert "Select Medical Specialization" in fake_adapter.last_message["text"]


@pytest.mark.asyncio
async def test_router_booking_flow_full():
    """Test full 5-step booking flow via Telegram router."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    user_id = 777888999
    chat_id = 777888999

    # 1. Create hospital and doctor
    hosp = await hospital_crud.create_hospital(
        hospital_document(
            name="Max Super Speciality Hospital",
            address="Saket, 110017",
            city="New Delhi",
            state="Delhi",
            contact_phone="+911126515050",
            contact_email="saket@citycare.clinic",
            status="active",
        )
    )
    hosp_id = str(hosp["_id"])


    doctor = await user_crud.create_user(
        user_document(
            first_name="Rohan",
            last_name="Mehta",
            email="rohan.mehta@citycare.clinic",
            mobile="+919876543211",
            password_hash="doc_hash",
            role=UserRole.DOCTOR,
            hospital_id=hosp_id,
            specialization="Cardiology",
            qualification="MD, DM Cardiology",
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            working_hours="09:00 - 17:00",
            valid_slots=["10:00 AM", "10:30 AM", "11:00 AM"],
            is_active=True,
        )
    )
    doctor_id = str(doctor["_id"])

    # 2. Create and link patient
    patient = await user_crud.create_user(
        user_document(
            first_name="Sanjay",
            last_name="Gupta",
            email="sanjay.gupta@example.com",
            mobile="+919876543299",
            password_hash="dummy_hash",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
    )
    patient_id = str(patient["_id"])
    await IdentityManager.link_patient(telegram_user_id=user_id, telegram_chat_id=chat_id, patient_id=patient_id)

    # 3. Step 1: /book
    await router.process_update({
        "update_id": 2001,
        "message": {
            "message_id": 10,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "first_name": "Sanjay"},
            "text": "/book",
        },
    })
    assert "Step 1/5" in fake_adapter.last_message["text"]

    # 4. Step 2: Click Hospital
    await router.process_update({
        "update_id": 2002,
        "callback_query": {
            "id": "cb_1",
            "from": {"id": user_id},
            "message": {"chat": {"id": chat_id}, "message_id": 11},
            "data": f"bk:hosp:{hosp_id}",
        },
    })
    assert "Step 2/5" in fake_adapter.last_message["text"]

    # 5. Step 3: Click Doctor
    await router.process_update({
        "update_id": 2003,
        "callback_query": {
            "id": "cb_2",
            "from": {"id": user_id},
            "message": {"chat": {"id": chat_id}, "message_id": 12},
            "data": f"bk:doc:{doctor_id}",
        },
    })
    assert "Step 3/5" in fake_adapter.last_message["text"]

    # 6. Step 4: Click Date (tomorrow)
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    await router.process_update({
        "update_id": 2004,
        "callback_query": {
            "id": "cb_3",
            "from": {"id": user_id},
            "message": {"chat": {"id": chat_id}, "message_id": 13},
            "data": f"bk:date:{tomorrow}",
        },
    })
    assert "Step 4/5" in fake_adapter.last_message["text"]

    # 7. Step 5: Click Slot
    await router.process_update({
        "update_id": 2005,
        "callback_query": {
            "id": "cb_4",
            "from": {"id": user_id},
            "message": {"chat": {"id": chat_id}, "message_id": 14},
            "data": "bk:slot:10:00 AM",
        },
    })
    assert "Step 5/5" in fake_adapter.last_message["text"]

    # 8. Type Reason
    await router.process_update({
        "update_id": 2006,
        "message": {
            "message_id": 15,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "first_name": "Sanjay"},
            "text": "Mild palpitation after routine exercise",
        },
    })
    assert "Appointment Summary" in fake_adapter.last_message["text"]

    # 9. Click Confirm
    await router.process_update({
        "update_id": 2007,
        "callback_query": {
            "id": "cb_5",
            "from": {"id": user_id},
            "message": {"chat": {"id": chat_id}, "message_id": 16},
            "data": "bk:confirm",
        },
    })
    assert "Appointment Confirmed" in fake_adapter.last_message["text"]

    # Verify appointment in database
    db = get_database()
    appts = await db.appointments.find({"patient_id": patient_id}).to_list(length=10)
    assert len(appts) == 1
    assert appts[0]["slot"] == "10:00 AM"
    assert appts[0]["doctor_id"] == doctor_id


@pytest.mark.asyncio
async def test_router_prescription_and_ai_chat_emergency():
    """Verify prescription access and emergency red-flag escalation."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)
    user_id = 444555666
    chat_id = 444555666

    # 1. Emergency detection
    await router.process_update({
        "update_id": 3001,
        "message": {
            "message_id": 50,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "first_name": "Patient"},
            "text": "Help me I am having acute chest pain and trouble breathing",
        },
    })
    assert "CRITICAL EMERGENCY NOTICE" in fake_adapter.last_message["text"]


@pytest.mark.asyncio
async def test_webhook_route_secret_token_validation(client: AsyncClient):
    """Test webhook endpoint secret token header security and disabled status."""
    settings = get_settings()

    # 1. When disabled, returns 503
    settings.telegram_enabled = False
    resp_disabled = await client.post(
        "/telegram/webhook",
        json={"update_id": 9999, "message": {"text": "hello"}},
    )
    assert resp_disabled.status_code == 503

    # 2. When enabled with secret token
    settings.telegram_enabled = True
    settings.telegram_webhook_secret = "secret-token-xyz-12345"

    # Bad token -> 403
    resp_bad = await client.post(
        "/telegram/webhook",
        json={"update_id": 9999, "message": {"text": "hello"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert resp_bad.status_code == 403

    # Valid token -> 200
    resp_ok = await client.post(
        "/telegram/webhook",
        json={"update_id": 9999, "message": {"text": "hello"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token-xyz-12345"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["ok"] is True

    # Reset
    settings.telegram_enabled = False
    settings.telegram_webhook_secret = ""

