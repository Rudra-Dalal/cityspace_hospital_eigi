"""Master Telegram dispatcher for commands, messages, and callback queries."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Union

from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.database import get_database
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.flows.booking_flow import (
    start_booking_flow,
    handle_booking_callback,
    handle_booking_text_message,
    show_patient_appointments,
    handle_appointment_cancel_callback,
)
from telegram_gateway.flows.chat_flow import handle_ai_health_chat
from telegram_gateway.flows.discovery_flow import (
    show_hospitals,
    show_hospital_detail,
    show_doctors,
    show_specializations,
)
from telegram_gateway.flows.linking_flow import (
    start_linking_flow,
    handle_linking_text_message,
)
from telegram_gateway.flows.prescriptions_flow import (
    show_patient_prescriptions,
    show_prescription_detail,
    send_prescription_pdf,
)
from telegram_gateway.flows.registration_flow import (
    start_registration_flow,
    handle_registration_callback,
    handle_registration_text_message,
)
from telegram_gateway.assistant import ConversationalAssistant
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.keyboards import main_menu_keyboard
from telegram_gateway.models import TelegramFlowType, TelegramIdempotencyStatus
from telegram_gateway.rate_limiter import MongoRateLimiter
from telegram_gateway.session_manager import SessionManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


HELP_TEXT = """🏥 *CityCare Patient Assistant Guide*

Welcome to CityCare Clinic & Hospital Platform\\! You can use these commands anytime:

📅 *Appointments & Discovery:*
• /book \\- Schedule a doctor appointment
• /hospitals \\- Explore clinic & hospital branches
• /doctors \\- View specialists & working days
• /specializations \\- Browse medical departments
• /facilities \\- Hospital facilities & emergency info
• /my\\_appointments \\- View or cancel your appointments

💊 *Prescriptions & Medical Records:*
• /my\\_prescriptions \\- Access diagnoses & download PDFs

👤 *Account Management:*
• /link \\- Link an existing CityCare patient account
• /register \\- Register as a new patient
• /status \\- View account & verification status
• /cancel or /reset \\- Clear active flow and return to menu

💬 *AI Health & Clinic Assistant:*
Simply type any health inquiry, clinic policy question, or medication query in chat to receive grounded assistance\\."""


async def _claim_update_idempotency(update_id: int) -> bool:
    """
    Atomically claim an update ID to prevent duplicate processing across retries/workers.
    Allows retrying updates that previously failed, but rejects duplicates that are processing or completed.
    Returns True if claimed, False if duplicate/in-progress/completed.
    """
    try:
        db = get_database()
    except RuntimeError:
        return True  # Fallback for unit tests without initialized DB fixture

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    try:
        # 1. If this update previously failed, allow retry
        retry_record = await db.telegram_idempotency.find_one_and_update(
            {
                "update_id": update_id,
                "status": TelegramIdempotencyStatus.FAILED.value,
            },
            {
                "$set": {
                    "status": TelegramIdempotencyStatus.PROCESSING.value,
                    "processed_at": now,
                    "expires_at": expires_at,
                    "error": None,
                }
            },
        )
        if retry_record:
            logger.info("Retrying previously failed Telegram update %s", update_id)
            return True

        # 2. Otherwise insert as new processing record
        await db.telegram_idempotency.insert_one({
            "update_id": update_id,
            "status": TelegramIdempotencyStatus.PROCESSING.value,
            "processed_at": now,
            "expires_at": expires_at,
        })
        return True
    except DuplicateKeyError:
        logger.info("Duplicate Telegram update %s dropped via idempotency check", update_id)
        return False
    except Exception as exc:
        logger.error("Idempotency database error: %s", exc)
        return True



async def _mark_update_completed(update_id: int, status: str = TelegramIdempotencyStatus.COMPLETED.value, error: Optional[str] = None) -> None:
    """Update idempotency record status upon workflow completion."""
    try:
        db = get_database()
        await db.telegram_idempotency.update_one(
            {"update_id": update_id},
            {"$set": {"status": status, "error": error}},
        )
    except Exception:
        pass


class TelegramRouter:
    """Dispatches Telegram updates to the appropriate flows with full security validation."""

    def __init__(self, adapter: Optional[TelegramAdapter] = None):
        self.adapter = adapter or TelegramAdapter()
        self.assistant = ConversationalAssistant(adapter=self.adapter)

    async def process_update(self, update: Dict[str, Any]) -> None:
        """Entry point for processing a single Telegram update dictionary."""
        update_id = update.get("update_id", 0)
        if update_id:
            claimed = await _claim_update_idempotency(update_id)
            if not claimed:
                return

        try:
            if "message" in update:
                await self._handle_message(update["message"])
            elif "callback_query" in update:
                await self._handle_callback_query(update["callback_query"])
            await _mark_update_completed(update_id, TelegramIdempotencyStatus.COMPLETED.value)
        except Exception as exc:
            logger.error("Error processing Telegram update %s: %s", update_id, exc, exc_info=True)
            await _mark_update_completed(update_id, TelegramIdempotencyStatus.FAILED.value, error=str(exc))

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        from_user = message.get("from", {})
        user_id = from_user.get("id")
        text = (message.get("text") or "").strip()
        thread_id = message.get("message_thread_id")

        if not chat_id or not user_id:
            return

        # 1. Private chat enforcement
        if chat_type != "private":
            await self.adapter.send_message(
                chat_id=chat_id,
                text="ℹ️ CityCare Patient Assistant is only available in private 1\\-on\\-1 chats for patient privacy\\.",
            )
            return

        # 2. Allowlist check (if configured)
        settings = get_settings()
        allowed_users = settings.telegram_allowed_users_set
        if allowed_users and user_id not in allowed_users:
            logger.warning("Unauthorized user %s attempted Telegram interaction", user_id)
            await self.adapter.send_message(
                chat_id=chat_id,
                text="🔒 Access to this preview instance is restricted\\. Please contact the clinic administrator\\.",
            )
            return

        # 3. Distributed Rate Limiter
        allowed = await MongoRateLimiter.is_allowed(
            user_id=user_id,
            action="msg",
            limit=settings.telegram_rate_limit_per_minute,
            window_seconds=60,
        )
        if not allowed:
            await self.adapter.send_message(
                chat_id=chat_id,
                text="⚠️ *Rate Limit Exceeded*\n\nYou are sending messages too quickly\\. Please wait a moment before trying again\\.",
            )
            return

        # 4. Resolve persistent session & linked patient identity
        identity, patient = await IdentityManager.resolve_identity(user_id)
        patient_id = identity.patient_id if (identity and identity.verified) else None

        session = await SessionManager.get_or_create_session(
            telegram_user_id=user_id,
            chat_id=chat_id,
            thread_id=thread_id,
            chat_type=chat_type,
            patient_id=patient_id,
        )

        # 5. Handle Global Slash Commands
        lower_text = text.lower()
        if lower_text in ("/cancel", "/reset"):
            await SessionManager.clear_flow(session.session_key)
            await self.adapter.send_message(
                chat_id=chat_id,
                text="🔄 *Workflow Reset*\n\nActive operations have been cleared\\. How can CityCare assist you today?",
                reply_markup=main_menu_keyboard(is_verified=bool(patient)),
            )
            return

        if lower_text == "/start":
            await SessionManager.clear_flow(session.session_key)
            greeting = f"Welcome to CityCare, *{escape_markdown(from_user.get('first_name', 'Patient'))}*\\!"
            status_line = "✅ *Linked Patient Account*" if patient else "ℹ️ *Guest Patient* \\(Use /link or /register\\)"

            welcome_msg = f"""🏥 *CityCare Hospital Patient Assistant*

{greeting}
{status_line}

I can help you book specialist appointments, explore hospital branches, access medical prescriptions, and answer healthcare questions\\.

Please select an option below:"""

            await self.adapter.send_message(
                chat_id=chat_id,
                text=welcome_msg,
                reply_markup=main_menu_keyboard(is_verified=bool(patient)),
            )
            return

        if lower_text == "/help":
            await self.adapter.send_message(
                chat_id=chat_id,
                text=HELP_TEXT,
                reply_markup=main_menu_keyboard(is_verified=bool(patient)),
            )
            return

        if lower_text == "/status":
            if patient:
                p_name = escape_markdown(f"{patient.get('first_name')} {patient.get('last_name')}")
                p_email = escape_markdown(patient.get("email"))
                p_mob = escape_markdown(patient.get("mobile"))
                status_text = f"""👤 *Account Status: Verified*

• *Patient Name:* {p_name}
• *Email:* {p_email}
• *Mobile:* {p_mob}
• *Telegram User ID:* `{user_id}`

All features including appointment booking, appointment history, and prescription access are active\\."""
            else:
                status_text = f"""👤 *Account Status: Unverified Guest*

• *Telegram User ID:* `{user_id}`
• *Status:* Not Linked

Please use /link to link your existing CityCare account or /register to create a new patient account\\."""

            await self.adapter.send_message(
                chat_id=chat_id,
                text=status_text,
                reply_markup=main_menu_keyboard(is_verified=bool(patient)),
            )
            return

        if lower_text == "/hospitals":
            await show_hospitals(self.adapter, chat_id)
            return

        if lower_text in ("/facilities", "/info"):
            await show_hospitals(self.adapter, chat_id)
            return

        if lower_text == "/doctors":
            await show_doctors(self.adapter, chat_id)
            return

        if lower_text == "/specializations":
            await show_specializations(self.adapter, chat_id)
            return

        if lower_text == "/book":
            await start_booking_flow(self.adapter, chat_id, session, patient)
            return

        if lower_text == "/my_appointments":
            await show_patient_appointments(self.adapter, chat_id, patient)
            return

        if lower_text == "/my_prescriptions":
            await show_patient_prescriptions(self.adapter, chat_id, patient)
            return

        if lower_text == "/link":
            await start_linking_flow(self.adapter, chat_id, session, patient)
            return

        if lower_text == "/register":
            await start_registration_flow(self.adapter, chat_id, session, patient)
            return

        # 6. Active Workflow Text Handlers
        if session.current_flow == TelegramFlowType.BOOKING.value:
            handled = await handle_booking_text_message(
                adapter=self.adapter,
                chat_id=chat_id,
                session=session,
                patient=patient,
                text=text,
            )
            if handled:
                return

        if session.current_flow == TelegramFlowType.LINKING.value:
            handled = await handle_linking_text_message(
                adapter=self.adapter,
                chat_id=chat_id,
                session=session,
                user_id=user_id,
                text=text,
            )
            if handled:
                return

        if session.current_flow == TelegramFlowType.REGISTRATION.value:
            handled = await handle_registration_text_message(
                adapter=self.adapter,
                chat_id=chat_id,
                session=session,
                user_id=user_id,
                text=text,
            )
            if handled:
                return

        # 7. Conversational Assistant (Natural understanding, Medihub services, AI health)
        await self.assistant.handle_message(
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            session=session,
            patient=patient,
            from_user=from_user,
        )

    async def _handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        cq_id = callback_query.get("id")
        from_user = callback_query.get("from", {})
        user_id = from_user.get("id")
        message = callback_query.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        data = callback_query.get("data", "")
        thread_id = message.get("message_thread_id")

        if not cq_id or not user_id or not chat_id:
            return

        # Rate Limiting
        settings = get_settings()
        allowed = await MongoRateLimiter.is_allowed(
            user_id=user_id,
            action="cb",
            limit=settings.telegram_rate_limit_per_minute,
            window_seconds=60,
        )
        if not allowed:
            await self.adapter.answer_callback_query(cq_id, text="Please wait before clicking again.", show_alert=True)
            return

        # Resolve persistent session & identity
        identity, patient = await IdentityManager.resolve_identity(user_id)
        patient_id = identity.patient_id if (identity and identity.verified) else None

        session = await SessionManager.get_or_create_session(
            telegram_user_id=user_id,
            chat_id=chat_id,
            thread_id=thread_id,
            chat_type="private",
            patient_id=patient_id,
        )

        # 1. Navigation callbacks
        if data == "nav:main":
            await SessionManager.clear_flow(session.session_key)
            await self.adapter.answer_callback_query(cq_id)
            await self.adapter.send_message(
                chat_id=chat_id,
                text="🏥 *CityCare Main Menu*",
                reply_markup=main_menu_keyboard(is_verified=bool(patient)),
            )
            return

        if data == "nav:hospitals":
            await self.adapter.answer_callback_query(cq_id)
            await show_hospitals(self.adapter, chat_id)
            return

        if data == "nav:doctors":
            await self.adapter.answer_callback_query(cq_id)
            await show_doctors(self.adapter, chat_id)
            return

        if data == "nav:specializations":
            await self.adapter.answer_callback_query(cq_id)
            await show_specializations(self.adapter, chat_id)
            return

        if data == "nav:facilities":
            await self.adapter.answer_callback_query(cq_id)
            await show_hospitals(self.adapter, chat_id)
            return

        if data == "nav:book":
            await self.adapter.answer_callback_query(cq_id)
            await start_booking_flow(self.adapter, chat_id, session, patient)
            return

        if data == "nav:my_appointments":
            await self.adapter.answer_callback_query(cq_id)
            await show_patient_appointments(self.adapter, chat_id, patient)
            return

        if data == "nav:my_prescriptions":
            await self.adapter.answer_callback_query(cq_id)
            await show_patient_prescriptions(self.adapter, chat_id, patient)
            return

        if data == "nav:link":
            await self.adapter.answer_callback_query(cq_id)
            await start_linking_flow(self.adapter, chat_id, session, patient)
            return

        if data == "nav:register":
            await self.adapter.answer_callback_query(cq_id)
            await start_registration_flow(self.adapter, chat_id, session, patient)
            return

        if data == "nav:help":
            await self.adapter.answer_callback_query(cq_id)
            await self.adapter.send_message(
                chat_id=chat_id,
                text=HELP_TEXT,
                reply_markup=main_menu_keyboard(is_verified=bool(patient)),
            )
            return

        # 2. View Hospital detail
        if data.startswith("view:hosp:"):
            h_id = data.split("view:hosp:")[1].strip()
            await self.adapter.answer_callback_query(cq_id)
            await show_hospital_detail(self.adapter, chat_id, h_id)
            return

        # 3. Booking flow callbacks
        if data.startswith("bk:"):
            await handle_booking_callback(
                adapter=self.adapter,
                chat_id=chat_id,
                session=session,
                patient=patient,
                callback_data=data,
                callback_query_id=cq_id,
            )
            return

        # 4. Registration consent callbacks
        if data.startswith("reg:"):
            await handle_registration_callback(
                adapter=self.adapter,
                chat_id=chat_id,
                session=session,
                user_id=user_id,
                callback_data=data,
                callback_query_id=cq_id,
            )
            return

        # 5. Prescriptions callbacks
        if data.startswith("rx:view:"):
            rx_id = data.split("rx:view:")[1].strip()
            await show_prescription_detail(
                adapter=self.adapter,
                chat_id=chat_id,
                patient=patient,
                prescription_id=rx_id,
                callback_query_id=cq_id,
            )
            return

        if data.startswith("rx:pdf:"):
            rx_id = data.split("rx:pdf:")[1].strip()
            await send_prescription_pdf(
                adapter=self.adapter,
                chat_id=chat_id,
                patient=patient,
                prescription_id=rx_id,
                callback_query_id=cq_id,
            )
            return

        # 6. Appointment cancellation callbacks
        if data.startswith("appt:cancel:"):
            appt_id = data.split("appt:cancel:")[1].strip()
            await handle_appointment_cancel_callback(
                adapter=self.adapter,
                chat_id=chat_id,
                patient=patient,
                appointment_id=appt_id,
                callback_query_id=cq_id,
            )
            return

        # Default fallback
        await self.adapter.answer_callback_query(cq_id)
