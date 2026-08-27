"""Centralized conversational policy and keyboard display manager for Medihub Telegram Assistant."""

from enum import Enum
from typing import Any, Dict, Optional, Union
from telegram_gateway.adapter import TelegramAdapter
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationMode(str, Enum):
    """Conversational lifecycle modes."""
    IDLE = "idle"
    SYMPTOM_INTAKE = "symptom_intake"
    SYMPTOM_DISCUSSION = "symptom_discussion"
    DOCTOR_DISCOVERY = "doctor_discovery"
    DOCTOR_SELECTION = "doctor_selection"
    HOSPITAL_SELECTION = "hospital_selection"
    DATE_SELECTION = "date_selection"
    SLOT_SELECTION = "slot_selection"
    REASON_COLLECTION = "reason_collection"
    BOOKING_CONFIRMATION = "booking_confirmation"
    REGISTRATION = "registration"
    REGISTRATION_CONFIRMATION = "registration_confirmation"
    PRESCRIPTION_VIEW = "prescription_view"
    APPOINTMENT_VIEW = "appointment_view"


def should_show_keyboard(
    intent: str,
    conversation_mode: Optional[str] = None,
    flow_step: Optional[str] = None,
    options_count: int = 0,
    confidence: float = 1.0,
) -> bool:
    """
    Centralized policy determining when inline keyboards may be shown.

    PRIMARY UX PRINCIPLE: Natural chat first, buttons second.
    Keyboards are optional shortcuts and should never be the primary interaction mechanism.

    NO KEYBOARD:
    - symptom intake / discussion
    - open-ended questions
    - normal conversation / clarification questions
    - casual chat
    - missing-information questions ('I need a doctor')
    - conversational follow-ups
    - context switching ('Actually someone else', 'Actually Friday', 'I changed my mind')
    - registration field collection ('enter_name', 'enter_dob', 'enter_email', 'enter_mobile')
    - emergency alerts
    - cancellation confirmations

    OPTIONAL SHORTCUT / KEYBOARD ALLOWED:
    - concrete doctor selection (when 1+ doctors are retrieved)
    - concrete available slots
    - concrete date selection
    - concrete hospital selection
    - registration confirmation card
    - appointment booking confirmation card
    - prescription PDF download action
    - active appointments view with cancel buttons
    """
    # Explicit no-keyboard intents and steps
    no_keyboard_intents = {
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
    }
    if intent in no_keyboard_intents:
        return False

    no_keyboard_steps = {
        "enter_name",
        "enter_dob",
        "enter_email",
        "enter_mobile",
        "enter_reason",
        "awaiting_symptoms",
    }
    if flow_step in no_keyboard_steps:
        return False

    if conversation_mode in (
        ConversationMode.SYMPTOM_INTAKE.value,
        ConversationMode.SYMPTOM_DISCUSSION.value,
        ConversationMode.REASON_COLLECTION.value,
    ):
        return False

    # Allowed keyboards for concrete actionable steps
    if flow_step in ("confirm_booking", "confirm_registration"):
        return True

    if intent in ("confirm_booking", "confirm_registration"):
        return True

    if conversation_mode == ConversationMode.DOCTOR_SELECTION.value and options_count > 0:
        return True

    if conversation_mode == ConversationMode.SLOT_SELECTION.value and options_count > 0:
        return True

    if conversation_mode == ConversationMode.DATE_SELECTION.value and options_count > 0:
        return True

    if conversation_mode == ConversationMode.HOSPITAL_SELECTION.value and options_count > 0:
        return True

    if conversation_mode == ConversationMode.APPOINTMENT_VIEW.value and options_count > 0:
        return True

    if conversation_mode == ConversationMode.PRESCRIPTION_VIEW.value and options_count > 0:
        return True

    if intent == "hospital_info" and options_count > 0:
        return True

    if intent == "download_prescription":
        return True

    # Fallback to no keyboard to prevent keyboard spam
    return False


async def clear_stale_keyboard(
    adapter: TelegramAdapter,
    chat_id: int,
    flow_data_or_session: Union[Dict[str, Any], Any],
) -> None:
    """Remove obsolete inline keyboard from the prior message if present."""
    from telegram_gateway.models import TelegramSession

    is_session = isinstance(flow_data_or_session, TelegramSession)
    flow_data = flow_data_or_session.flow_data if is_session else flow_data_or_session

    if not isinstance(flow_data, dict):
        return

    last_msg_id = flow_data.get("last_keyboard_msg_id")
    if last_msg_id:
        try:
            await adapter.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=last_msg_id,
                reply_markup=None,
            )
        except Exception as exc:
            logger.debug("Failed to clear stale keyboard msg %s: %s", last_msg_id, exc)
        flow_data.pop("last_keyboard_msg_id", None)

        if is_session:
            try:
                from app.core.database import get_database
                db = get_database()
                await db.telegram_sessions.update_one(
                    {"session_key": flow_data_or_session.session_key},
                    {"$unset": {"flow_data.last_keyboard_msg_id": ""}},
                )
            except Exception as exc:
                logger.debug("Failed to persist cleared keyboard in session: %s", exc)


async def send_conversational_response(
    adapter: TelegramAdapter,
    chat_id: int,
    text: str,
    session: Optional[Any] = None,
    flow_data: Optional[Dict[str, Any]] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = "MarkdownV2",
    clear_stale: bool = True,
) -> Dict[str, Any]:
    """
    Send a message with centralized policy enforcement.
    Clears any prior stale keyboard on the chat, sends the new message,
    and records the new message_id in flow_data if a keyboard was attached.
    """
    active_flow_data = (session.flow_data if session else flow_data)
    if active_flow_data is None:
        active_flow_data = {}

    if clear_stale:
        await clear_stale_keyboard(adapter, chat_id, session if session else active_flow_data)

    resp = await adapter.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )

    if reply_markup and isinstance(resp, dict):
        result_payload = resp.get("result")
        msg_id = (
            result_payload.get("message_id")
            if isinstance(result_payload, dict)
            else resp.get("message_id")
        )
        if msg_id:
            active_flow_data["last_keyboard_msg_id"] = msg_id
            if session:
                session.flow_data = active_flow_data
                try:
                    from app.core.database import get_database
                    db = get_database()
                    await db.telegram_sessions.update_one(
                        {"session_key": session.session_key},
                        {"$set": {"flow_data.last_keyboard_msg_id": msg_id}},
                    )
                except Exception as exc:
                    logger.debug("Failed to record last_keyboard_msg_id in session: %s", exc)

    return resp
