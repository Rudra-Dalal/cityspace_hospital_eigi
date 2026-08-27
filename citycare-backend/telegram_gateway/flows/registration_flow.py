"""New patient registration workflow with consent tracking and secure activation."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.cruds import user_crud
from app.services.registration_service import register_patient
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.keyboards import (
    consent_keyboard,
    main_menu_keyboard,
    compact_menu_keyboard,
    registration_summary_keyboard,
)
from telegram_gateway.conversation_policy import clear_stale_keyboard, send_conversational_response
from telegram_gateway.models import TelegramFlowType, TelegramSession
from telegram_gateway.session_manager import SessionManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def show_registration_summary(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    flow_data: Dict[str, Any],
) -> None:
    """Present concise registration summary card before patient creation."""
    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.REGISTRATION.value,
        flow_step="confirm_registration",
        flow_data=flow_data,
    )

    name_esc = escape_markdown(f"{flow_data.get('first_name', '')} {flow_data.get('last_name', '')}".strip())
    dob_esc = escape_markdown(flow_data.get("dob", "Not specified"))
    email_esc = escape_markdown(flow_data.get("email", ""))
    mob_esc = escape_markdown(flow_data.get("mobile", ""))

    summary = f"""Here's what I have:

• *Name:* {name_esc}
• *Date of Birth:* {dob_esc}
• *Email:* {email_esc}
• *Mobile:* {mob_esc}

Would you like me to create your patient profile?"""

    await send_conversational_response(
        adapter=adapter,
        chat_id=chat_id,
        text=summary,
        session=session,
        reply_markup=registration_summary_keyboard(),
    )


async def _finalize_registration_flow(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    user_id: int,
    flow_data: Dict[str, Any],
) -> None:
    """Create patient record, link Telegram identity, and resume pending bookings."""
    now = datetime.now(timezone.utc)
    consent_obj = {
        "given": True,
        "timestamp": now.isoformat(),
        "policy_version": "v1.0",
        "platform": "telegram",
        "dob": flow_data.get("dob"),
    }

    try:
        patient_record = await register_patient(
            payload={
                "first_name": flow_data["first_name"],
                "last_name": flow_data["last_name"],
                "email": flow_data["email"],
                "mobile": flow_data["mobile"],
                "password": "",  # Generates activation token
            },
            consent=consent_obj,
            allow_activation_token=True,
        )
    except Exception as exc:
        logger.error("Registration error in flow: %s", exc)
        err_msg = escape_markdown(str(exc))
        await adapter.send_message(
            chat_id=chat_id,
            text=f"❌ *Registration Error:* {err_msg}",
            reply_markup=main_menu_keyboard(is_verified=False),
        )
        await SessionManager.clear_flow(session.session_key)
        return

    patient_id = patient_record["id"]

    await IdentityManager.link_patient(
        telegram_user_id=user_id,
        telegram_chat_id=chat_id,
        patient_id=patient_id,
        consent=consent_obj,
    )

    await SessionManager.set_patient_id(session.session_key, patient_id)

    p_name = escape_markdown(f"{patient_record.get('first_name')} {patient_record.get('last_name')}")
    act_url = patient_record.get("activation_url")
    act_url_esc = escape_markdown(act_url) if act_url else ""

    welcome_msg = f"""🎉 *Registration Successful!*

Welcome to CityCare, *{p_name}*\\! Your Telegram account is now linked\\.

🔑 *Web Portal Password Setup:*
To log in via the web browser portal, click the link below to set your password:
[Set Web Password]({act_url_esc})

_This link is valid for 48 hours\\. You can use all Telegram bot features immediately without setting a web password\\._"""

    pending = flow_data.get("pending_booking")
    if pending:
        await adapter.send_message(chat_id=chat_id, text=welcome_msg)

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="confirm_booking",
            flow_data=pending,
        )

        h_name = escape_markdown(pending.get("hospital_name", "Central Clinic Branch"))
        d_name = escape_markdown(pending.get("doctor_name", "Specialist Physician"))
        date_val = escape_markdown(pending.get("date", ""))
        slot_val = escape_markdown(pending.get("slot", ""))
        reason_esc = escape_markdown(pending.get("reason", "Consultation"))

        from telegram_gateway.keyboards import confirmation_keyboard
        resume_text = f"""Now, let's complete your appointment booking:

🏥 *Hospital:* {h_name}
👨‍⚕️ *Doctor:* {d_name}
📅 *Date:* {date_val}
⏰ *Time:* {slot_val}
📝 *Reason:* {reason_esc}

Would you like to confirm this booking?"""

        await send_conversational_response(
            adapter=adapter,
            chat_id=chat_id,
            text=resume_text,
            session=session,
            reply_markup=confirmation_keyboard(),
        )
    else:
        await SessionManager.clear_flow(session.session_key)
        await send_conversational_response(
            adapter=adapter,
            chat_id=chat_id,
            text=welcome_msg,
            session=session,
            reply_markup=compact_menu_keyboard(is_verified=True),
        )


async def start_registration_flow(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    patient: Optional[Dict[str, Any]],
    initial_entities: Optional[Dict[str, Any]] = None,
) -> None:
    """Start registration flow for new patients with optional extracted entities."""
    if patient:
        p_name = escape_markdown(f"{patient.get('first_name')} {patient.get('last_name')}")
        await adapter.send_message(
            chat_id=chat_id,
            text=f"ℹ️ *Already Registered*\n\nYou are already registered and linked as *{p_name}*\\.",
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return

    flow_data = dict(session.flow_data or {})
    if initial_entities:
        for k, v in initial_entities.items():
            if v and not flow_data.get(k):
                flow_data[k] = v

    # Check if all required fields are already extracted
    has_name = bool(flow_data.get("first_name") and flow_data.get("last_name"))
    has_email = bool(flow_data.get("email"))
    has_mobile = bool(flow_data.get("mobile"))

    if has_name and has_email and has_mobile:
        await show_registration_summary(adapter, chat_id, session, flow_data)
        return

    if has_name:
        first_name = escape_markdown(flow_data.get("first_name", ""))
        if not flow_data.get("dob"):
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.REGISTRATION.value,
                flow_step="enter_dob",
                flow_data=flow_data,
            )
            await adapter.send_message(
                chat_id=chat_id,
                text=f"Thanks, *{first_name}*\\! What is your date of birth? \\(e\\.g\\. `12 May 2004` or `DD/MM/YYYY`\\)",
            )
            return
        elif not has_email:
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.REGISTRATION.value,
                flow_step="enter_email",
                flow_data=flow_data,
            )
            await adapter.send_message(
                chat_id=chat_id,
                text=f"Thanks, *{first_name}*\\! What email address should we use for your patient profile?",
            )
            return

    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.REGISTRATION.value,
        flow_step="enter_name",
        flow_data=flow_data,
    )

    await adapter.send_message(
        chat_id=chat_id,
        text=(
            "📝 *New Patient Registration*\n\n"
            "Please enter your *Full Name* \\(e\\.g\\. `Rahul Sharma`\\):"
        ),
    )



async def handle_registration_callback(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    user_id: int,
    callback_data: str,
    callback_query_id: str,
) -> None:
    """Process consent, confirmation, and cancellation buttons during registration."""
    if callback_data in ("reg:cancel", "reg:consent_no"):
        await SessionManager.clear_flow(session.session_key)
        await adapter.answer_callback_query(callback_query_id, text="Registration cancelled")
        await adapter.send_message(
            chat_id=chat_id,
            text="❌ *Registration Cancelled*\n\nYour temporary registration details have been cleared\\. How else can I help you?",
        )
        return

    if callback_data == "reg:edit":
        await adapter.answer_callback_query(callback_query_id)
        await adapter.send_message(
            chat_id=chat_id,
            text="Which detail would you like to update? You can send your updated Name, Date of Birth, Email, or Mobile number\\.",
        )
        return

    if callback_data == "reg:confirm":
        await adapter.answer_callback_query(callback_query_id)
        flow_data = dict(session.flow_data or {})
        await _finalize_registration_flow(adapter, chat_id, session, user_id, flow_data)
        return

    if callback_data == "reg:consent_yes":
        flow_data = dict(session.flow_data or {})
        now = datetime.now(timezone.utc)
        flow_data["consent"] = {
            "given": True,
            "timestamp": now.isoformat(),
            "policy_version": "v1.0",
            "platform": "telegram",
        }

        # Dispatch OTP to email
        email = flow_data.get("email")
        if not email:
            await adapter.answer_callback_query(callback_query_id, text="Registration error. Please restart.", show_alert=True)
            return

        issued = await IdentityManager.issue_otp(
            telegram_user_id=user_id,
            target_type="email",
            target_value=email,
            purpose="register_patient",
            metadata=flow_data,
        )

        if not issued:
            await adapter.answer_callback_query(callback_query_id, text="Failed to send verification code.", show_alert=True)
            return

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_otp",
            flow_data=flow_data,
        )
        await adapter.answer_callback_query(callback_query_id)

        email_esc = escape_markdown(email)
        await adapter.send_message(
            chat_id=chat_id,
            text=(
                f"📩 *Verification Code Sent \\(Step 4/4\\)*\n\n"
                f"We sent a 6\\-digit verification code to `{email_esc}`\\.\n\n"
                f"Please enter the code to complete your registration:"
            ),
        )
        return


async def handle_registration_text_message(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    user_id: int,
    text: str,
) -> bool:
    """Process step-by-step or entity-extracted text inputs during patient registration."""
    if session.current_flow != TelegramFlowType.REGISTRATION.value:
        return False

    from telegram_gateway.assistant import extract_registration_entities

    flow_step = session.flow_step
    flow_data = dict(session.flow_data or {})
    input_str = text.strip()
    lower_str = input_str.lower()

    # Cancel check
    if re.search(r"^\b(cancel|no|stop|forget it)\b", lower_str):
        await SessionManager.clear_flow(session.session_key)
        await adapter.send_message(
            chat_id=chat_id,
            text="❌ *Registration Cancelled*\n\nYour temporary registration details have been cleared\\. How else can I help you?",
        )
        return True

    # Step: Confirmation Summary Card
    if flow_step == "confirm_registration":
        if re.search(r"^\b(yes|confirm|proceed|create|create profile|looks good|correct|agree|sure)\b", lower_str):
            await _finalize_registration_flow(adapter, chat_id, session, user_id, flow_data)
            return True
        if re.search(r"^\b(edit|change|update)\b", lower_str):
            await adapter.send_message(
                chat_id=chat_id,
                text="Which detail would you like to update? You can send your updated Name, Date of Birth, Email, or Mobile number\\.",
            )
            return True

    # Extract all recognizable entities from input string
    extracted = extract_registration_entities(input_str)
    for k, v in extracted.items():
        if v:
            flow_data[k] = v

    # Specific step fallbacks if not captured by general entity extractor
    if flow_step == "enter_name" and not flow_data.get("first_name"):
        parts = input_str.split(None, 1)
        if len(parts) >= 2 and all(p.isalpha() for p in parts):
            flow_data["first_name"] = parts[0].strip()
            flow_data["last_name"] = parts[1].strip()
        else:
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Please enter both your first and last name \\(e\\.g\\. `Rudra Dalal`\\):",
            )
            return True

    elif flow_step == "enter_dob" and not flow_data.get("dob"):
        # If user typed a date like "12 May 2004" or "12/05/2004"
        flow_data["dob"] = input_str

    elif flow_step == "enter_email" and not flow_data.get("email"):
        email_clean = input_str.lower()
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email_clean):
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Please enter a valid email address \\(e\\.g\\. `name@example.com`\\):",
            )
            return True
        existing = await user_crud.get_user_by_email(email_clean)
        if existing:
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ An account with this email already exists\\. Use /link to link your existing account\\.",
                reply_markup=main_menu_keyboard(is_verified=False),
            )
            await SessionManager.clear_flow(session.session_key)
            return True
        flow_data["email"] = email_clean

    elif flow_step == "enter_mobile" and not flow_data.get("mobile"):
        mob = input_str
        if not mob.startswith("+91") and re.fullmatch(r"[6-9]\d{9}", mob):
            mob = f"+91{mob}"
        if not re.fullmatch(r"\+91[6-9]\d{9}", mob):
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Mobile number must match `+91` followed by a 10-digit Indian number \\(e\\.g\\. `+919876543210`\\)\\.",
            )
            return True
        flow_data["mobile"] = mob

    # Check if all required fields are present
    has_name = bool(flow_data.get("first_name") and flow_data.get("last_name"))
    has_email = bool(flow_data.get("email"))
    has_mobile = bool(flow_data.get("mobile"))

    if has_name and has_email and has_mobile:
        await show_registration_summary(adapter, chat_id, session, flow_data)
        return True

    # Missing fields progression
    if not has_name:
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_name",
            flow_data=flow_data,
        )
        await adapter.send_message(
            chat_id=chat_id,
            text="What is your full name? \\(e\\.g\\. `Rudra Dalal`\\)",
        )
        return True

    first_name = escape_markdown(flow_data.get("first_name", ""))
    if not flow_data.get("dob") and flow_step in ("enter_name", "enter_dob"):
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_dob",
            flow_data=flow_data,
        )
        await adapter.send_message(
            chat_id=chat_id,
            text=f"Thanks, *{first_name}*\\! What is your date of birth? \\(e\\.g\\. `12 May 2004`\\)",
        )
        return True

    if not has_email:
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_email",
            flow_data=flow_data,
        )
        await adapter.send_message(
            chat_id=chat_id,
            text=f"Thanks, *{first_name}*\\! And what email address should we use for your patient profile and prescriptions?",
        )
        return True

    if not has_mobile:
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_mobile",
            flow_data=flow_data,
        )
        await adapter.send_message(
            chat_id=chat_id,
            text="And what 10\\-digit mobile number should we use for your patient profile? \\(e\\.g\\. `+919876543210`\\)",
        )
        return True

    # Step 4: OTP Verification & Account Activation (for backwards compatibility)
    if flow_step == "enter_otp":
        raw_code = input_str.replace(" ", "")
        if not raw_code.isdigit() or len(raw_code) != 6:
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Please enter a 6-digit numeric verification code (e.g. 123456).",
            )
            return True

        is_valid, meta, error_msg = await IdentityManager.verify_otp(
            telegram_user_id=user_id,
            raw_code=raw_code,
            purpose="register_patient",
        )

        if not is_valid:
            err_esc = escape_markdown(error_msg)
            await adapter.send_message(chat_id=chat_id, text=f"❌ {err_esc}")
            return True

        reg_data = meta or flow_data
        consent_obj = reg_data.get("consent")

        # Create patient record and secure activation link
        try:
            patient_record = await register_patient(
                payload={
                    "first_name": reg_data["first_name"],
                    "last_name": reg_data["last_name"],
                    "email": reg_data["email"],
                    "mobile": reg_data["mobile"],
                    "password": "",  # Empty triggers secure activation token
                },
                consent=consent_obj,
                allow_activation_token=True,
            )
        except Exception as exc:
            logger.error("Registration error: %s", exc)
            await adapter.send_message(
                chat_id=chat_id,
                text="❌ An error occurred during registration. Please try again with /register.",
                reply_markup=main_menu_keyboard(is_verified=False),
            )
            await SessionManager.clear_flow(session.session_key)
            return True

        patient_id = patient_record["id"]

        # Link Telegram identity
        await IdentityManager.link_patient(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            patient_id=patient_id,
            consent=consent_obj,
        )

        await SessionManager.set_patient_id(session.session_key, patient_id)
        await SessionManager.clear_flow(session.session_key)

        p_name = escape_markdown(f"{patient_record.get('first_name')} {patient_record.get('last_name')}")
        act_url = patient_record.get("activation_url")
        act_url_esc = escape_markdown(act_url) if act_url else ""

        welcome_msg = f"""🎉 *Registration Successful!*

Welcome to CityCare, *{p_name}*\\! Your Telegram account is now linked\\.

🔑 *Web Portal Password Setup:*
To log in via the web browser portal, click the link below to set your password:
[Set Web Password]({act_url_esc})

_This link is valid for 48 hours\\. You can use all Telegram bot features immediately without setting a web password\\._"""

        await adapter.send_message(
            chat_id=chat_id,
            text=welcome_msg,
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return True

    return False
