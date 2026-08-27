"""Test suite for Centralized Conversational Policy and Stale Keyboard Pruning.

Verifies:
1. Pure chat-first UX rules in should_show_keyboard
2. Automatic stale keyboard pruning via editMessageReplyMarkup
3. Centralized send_conversational_response helper
4. Multi-turn chat tests ensuring buttons do not persist or clutter the dialog
"""

import pytest
import pytest_asyncio
from app.core.database import connect_to_mongo, ensure_indexes, get_database
from app.controllers.auth_controller import seed_doctor_if_missing
from app.core.migrate import run_migrations
from app.models.user_model import UserRole, user_document
from telegram_gateway.adapter import FakeTelegramAdapter
from telegram_gateway.conversation_policy import (
    ConversationMode,
    should_show_keyboard,
    clear_stale_keyboard,
    send_conversational_response,
)
from telegram_gateway.keyboards import (
    compact_menu_keyboard,
    doctors_keyboard,
    confirmation_keyboard,
    dates_keyboard,
)
from telegram_gateway.models import TelegramFlowType, TelegramSession
from telegram_gateway.router import TelegramRouter
from telegram_gateway.session_manager import SessionManager


@pytest_asyncio.fixture(autouse=True)
async def cleanup_policy_db():
    """Ensure clean test database state before and after each test."""
    await connect_to_mongo()
    await ensure_indexes()
    db = get_database()
    await db.hospitals.delete_many({})
    await db.users.delete_many({})
    await db.appointments.delete_many({})
    await db.prescriptions.delete_many({})
    await db.telegram_identities.delete_many({})
    await db.telegram_sessions.delete_many({})
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
    await db.telegram_idempotency.delete_many({})
    await db.telegram_rate_limits.delete_many({})


# ============================================================================
# 1. Unit Tests for should_show_keyboard
# ============================================================================

def test_should_show_keyboard_no_keyboard_intents():
    """Verify that open-ended chat, symptom intake, and resets reject keyboards."""
    no_keyboard_intents = [
        "symptom_intake_request",
        "symptom_discussion",
        "ask_doctor_preference",
        "missing_info",
        "general_chat",
        "context_switch",
        "change_mind_or_switch",
        "cancel_flow",
        "enter_reason",
        "emergency",
    ]
    for intent in no_keyboard_intents:
        assert should_show_keyboard(intent=intent) is False, f"Intent {intent} should not allow keyboards"


def test_should_show_keyboard_no_keyboard_steps():
    """Verify that intermediate text data collection steps strictly reject keyboards."""
    text_steps = [
        "enter_name",
        "enter_dob",
        "enter_email",
        "enter_mobile",
        "enter_reason",
        "awaiting_symptoms",
    ]
    for step in text_steps:
        assert should_show_keyboard(intent="book_appointment", flow_step=step) is False
        assert should_show_keyboard(intent="register_patient", flow_step=step) is False


def test_should_show_keyboard_conversation_modes():
    """Verify modes that forbid keyboards."""
    for mode in [
        ConversationMode.SYMPTOM_INTAKE.value,
        ConversationMode.SYMPTOM_DISCUSSION.value,
        ConversationMode.REASON_COLLECTION.value,
    ]:
        assert should_show_keyboard(intent="find_doctor", conversation_mode=mode) is False


def test_should_show_keyboard_concrete_allowed_steps():
    """Verify confirmation and concrete selections with options > 0 allow keyboards."""
    # Confirmations
    assert should_show_keyboard(intent="confirm_booking") is True
    assert should_show_keyboard(intent="confirm_registration") is True
    assert should_show_keyboard(intent="any", flow_step="confirm_booking") is True
    assert should_show_keyboard(intent="any", flow_step="confirm_registration") is True

    # Selections with options > 0
    assert should_show_keyboard(intent="find_doctor", conversation_mode=ConversationMode.DOCTOR_SELECTION.value, options_count=3) is True
    assert should_show_keyboard(intent="book_appointment", conversation_mode=ConversationMode.SLOT_SELECTION.value, options_count=5) is True
    assert should_show_keyboard(intent="book_appointment", conversation_mode=ConversationMode.DATE_SELECTION.value, options_count=3) is True
    assert should_show_keyboard(intent="hospitals", conversation_mode=ConversationMode.HOSPITAL_SELECTION.value, options_count=2) is True
    assert should_show_keyboard(intent="view_appointments", conversation_mode=ConversationMode.APPOINTMENT_VIEW.value, options_count=1) is True
    assert should_show_keyboard(intent="download_prescription", conversation_mode=ConversationMode.PRESCRIPTION_VIEW.value, options_count=1) is True

    # Selections with 0 options should NOT show keyboard
    assert should_show_keyboard(intent="find_doctor", conversation_mode=ConversationMode.DOCTOR_SELECTION.value, options_count=0) is False
    assert should_show_keyboard(intent="book_appointment", conversation_mode=ConversationMode.SLOT_SELECTION.value, options_count=0) is False


# ============================================================================
# 2. Unit Tests for clear_stale_keyboard & send_conversational_response
# ============================================================================

@pytest.mark.asyncio
async def test_clear_stale_keyboard_removes_buttons():
    """Verify clear_stale_keyboard strips the inline reply_markup from the fake adapter."""
    fake_adapter = FakeTelegramAdapter()

    # Bot sends a message with keyboard
    kb = compact_menu_keyboard()
    sent = await fake_adapter.send_message(chat_id=501, text="Choose an option", reply_markup=kb)
    msg_id = sent["result"]["message_id"]

    # Verify message initially has reply_markup
    assert fake_adapter.sent_messages[0]["reply_markup"] is not None

    flow_data = {"last_keyboard_msg_id": msg_id}
    await clear_stale_keyboard(fake_adapter, chat_id=501, flow_data_or_session=flow_data)

    # Verify reply markup was cleared on the message
    assert fake_adapter.sent_messages[0]["reply_markup"] is None
    assert "last_keyboard_msg_id" not in flow_data


@pytest.mark.asyncio
async def test_clear_stale_keyboard_with_session():
    """Verify clear_stale_keyboard works with a persistent TelegramSession."""
    fake_adapter = FakeTelegramAdapter()
    session = await SessionManager.get_or_create_session(
        telegram_user_id=888,
        chat_id=888,
    )

    sent = await fake_adapter.send_message(
        chat_id=888,
        text="Pick doctor",
        reply_markup=doctors_keyboard([]),
    )
    msg_id = sent["result"]["message_id"]

    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_doctor",
        flow_data={"last_keyboard_msg_id": msg_id},
    )
    updated_session = await SessionManager.get_session(session.session_key)

    await clear_stale_keyboard(fake_adapter, chat_id=888, flow_data_or_session=updated_session)

    # Checked that message was edited to None
    assert fake_adapter.sent_messages[0]["reply_markup"] is None

    reloaded = await SessionManager.get_session(session.session_key)
    assert "last_keyboard_msg_id" not in (reloaded.flow_data or {})


@pytest.mark.asyncio
async def test_send_conversational_response_clears_prior_and_stores_new():
    """Verify send_conversational_response removes previous buttons and tracks new keyboard."""
    fake_adapter = FakeTelegramAdapter()
    session = await SessionManager.get_or_create_session(telegram_user_id=777, chat_id=777)

    # First conversational response with keyboard
    await send_conversational_response(
        adapter=fake_adapter,
        chat_id=777,
        text="First question",
        session=session,
        reply_markup=compact_menu_keyboard(),
    )

    reloaded1 = await SessionManager.get_session(session.session_key)
    first_msg_id = reloaded1.flow_data.get("last_keyboard_msg_id")
    assert first_msg_id is not None
    assert fake_adapter.sent_messages[0]["reply_markup"] is not None

    # Second conversational response with another keyboard
    await send_conversational_response(
        adapter=fake_adapter,
        chat_id=777,
        text="Second question",
        session=reloaded1,
        reply_markup=confirmation_keyboard(),
    )

    # Verify first message's reply_markup was edited to None
    assert fake_adapter.sent_messages[0]["reply_markup"] is None
    # Verify second message has reply_markup
    assert fake_adapter.sent_messages[1]["reply_markup"] is not None

    reloaded2 = await SessionManager.get_session(session.session_key)
    assert reloaded2.flow_data.get("last_keyboard_msg_id") == fake_adapter.sent_messages[1]["message_id"]


# ============================================================================
# 3. Multi-turn Conversational Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_multi_turn_stale_keyboard_pruning_on_user_speech():
    """Turn 1 presents buttons. Turn 2 user speaks text. Buttons on Turn 1 message are pruned immediately."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    # 1. User says hi -> bot responds with compact_menu_keyboard
    await router.process_update({
        "update_id": 901,
        "message": {
            "message_id": 901,
            "chat": {"id": 601, "type": "private"},
            "from": {"id": 601, "first_name": "Rohan"},
            "text": "Hi there",
        },
    })

    assert len(fake_adapter.sent_messages) == 1
    msg1 = fake_adapter.sent_messages[0]
    assert msg1["reply_markup"] is not None, "Turn 1 greeting should have compact keyboard"

    # 2. User speaks naturally in Turn 2 (e.g. describes symptom)
    await router.process_update({
        "update_id": 902,
        "message": {
            "message_id": 902,
            "chat": {"id": 601, "type": "private"},
            "from": {"id": 601, "first_name": "Rohan"},
            "text": "I have a skin rash on my arms",
        },
    })

    # The first message's keyboard must now be stripped (None)
    assert msg1["reply_markup"] is None, "Stale keyboard on msg1 should have been pruned on Turn 2"


@pytest.mark.asyncio
async def test_cancellation_produces_no_keyboard_clutter():
    """Verify /cancel or 'cancel' resets the state with pure text, no dangling keyboards."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 910,
        "message": {
            "message_id": 910,
            "chat": {"id": 602, "type": "private"},
            "from": {"id": 602, "first_name": "Aman"},
            "text": "cancel",
        },
    })

    assert len(fake_adapter.sent_messages) == 1
    last = fake_adapter.last_message
    assert "cancelled" in last["text"].lower() or "workflow reset" in last["text"].lower()
    assert last.get("reply_markup") is None, "Cancel confirmation should not attach keyboards"


@pytest.mark.asyncio
async def test_emergency_alert_has_no_distracting_keyboards():
    """Emergency alerts must deliver immediate critical guidance without buttons."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 920,
        "message": {
            "message_id": 920,
            "chat": {"id": 603, "type": "private"},
            "from": {"id": 603, "first_name": "Priya"},
            "text": "Severe chest pain and shortness of breath",
        },
    })

    assert len(fake_adapter.sent_messages) == 1
    last = fake_adapter.last_message
    assert "EMERGENCY" in last["text"]
    assert last.get("reply_markup") is None, "Emergency response must not attach buttons"


@pytest.mark.asyncio
async def test_open_ended_doctor_query_does_not_spam_keyboards():
    """Query without specific doctor or department asks follow-up without spamming department keyboard."""
    fake_adapter = FakeTelegramAdapter()
    router = TelegramRouter(adapter=fake_adapter)

    await router.process_update({
        "update_id": 930,
        "message": {
            "message_id": 930,
            "chat": {"id": 604, "type": "private"},
            "from": {"id": 604, "first_name": "Meera"},
            "text": "Can you recommend a doctor?",
        },
    })

    assert len(fake_adapter.sent_messages) == 1
    last = fake_adapter.last_message
    assert "doctor in mind" in last["text"].lower() or "recommend" in last["text"].lower()
    assert last.get("reply_markup") is None, "Open-ended doctor inquiry must not attach button menus"
