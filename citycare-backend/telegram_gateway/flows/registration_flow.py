"""New patient registration workflow with consent tracking and secure activation."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.cruds import user_crud
from app.services.registration_service import register_patient
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.keyboards import consent_keyboard, main_menu_keyboard
from telegram_gateway.models import TelegramFlowType, TelegramSession
from telegram_gateway.session_manager import SessionManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def start_registration_flow(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    patient: Optional[Dict[str, Any]],
) -> None:
    """Start registration flow for new patients."""
    if patient:
        p_name = escape_markdown(f"{patient.get('first_name')} {patient.get('last_name')}")
        await adapter.send_message(
            chat_id=chat_id,
            text=f"ℹ️ *Already Registered*\n\nYou are already registered and linked as *{p_name}*\\.",
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return

    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.REGISTRATION.value,
        flow_step="enter_name",
        flow_data={},
    )

    await adapter.send_message(
        chat_id=chat_id,
        text=(
            "📝 *New Patient Registration \\(Step 1/4\\)*\n\n"
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
    """Process consent and cancellation buttons during registration."""
    if callback_data == "reg:consent_no":
        await SessionManager.clear_flow(session.session_key)
        await adapter.answer_callback_query(callback_query_id, text="Registration cancelled")
        await adapter.send_message(
            chat_id=chat_id,
            text="❌ *Registration Cancelled*\n\nConsent was not granted\\. Your temporary registration data has been cleared\\.",
            reply_markup=main_menu_keyboard(is_verified=False),
        )
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
    """Process step-by-step text inputs during patient registration."""
    if session.current_flow != TelegramFlowType.REGISTRATION.value:
        return False

    flow_step = session.flow_step
    flow_data = dict(session.flow_data or {})
    input_str = text.strip()

    # Step 1: Full Name
    if flow_step == "enter_name":
        parts = input_str.split(None, 1)
        if len(parts) < 2:
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Please enter both your first and last name \\(e\\.g\\. `Rahul Sharma`\\):",
            )
            return True

        flow_data["first_name"] = parts[0].strip()
        flow_data["last_name"] = parts[1].strip()

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_email",
            flow_data=flow_data,
        )

        await adapter.send_message(
            chat_id=chat_id,
            text="📧 *Step 2/4: Email Address*\n\nPlease enter your email address for appointment confirmations and prescriptions:",
        )
        return True

    # Step 2: Email Address
    if flow_step == "enter_email":
        email_clean = input_str.lower()
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email_clean):
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Please enter a valid email address (e.g. name@example.com):",
            )
            return True

        # Check existing email
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

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_mobile",
            flow_data=flow_data,
        )

        await adapter.send_message(
            chat_id=chat_id,
            text=(
                "📱 *Step 3/4: Mobile Number*\n\n"
                "Please enter your 10-digit Indian mobile number with +91 (e.g. `+919876543210`):"
            ),
        )
        return True

    # Step 3: Mobile Number
    if flow_step == "enter_mobile":
        mob = input_str
        if not mob.startswith("+91") and re.fullmatch(r"[6-9]\d{9}", mob):
            mob = f"+91{mob}"

        if not re.fullmatch(r"\+91[6-9]\d{9}", mob):
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Mobile number must match `+91` followed by a 10-digit Indian number (e.g. `+919876543210`).",
            )
            return True

        flow_data["mobile"] = mob

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="consent",
            flow_data=flow_data,
        )

        consent_text = f"""📋 *Patient Terms & Consent*

By registering with CityCare Health Services via Telegram:
1\\. You authorize CityCare to store your name, contact information, and appointment records securely\\.
2\\. You consent to receiving appointment updates and prescription summaries via this Telegram chat\\.
3\\. Medical prescriptions and clinical records remain confidential and protected under CityCare Clinical Privacy Policy v1\\.0\\.

Do you agree to these terms?"""

        await adapter.send_message(
            chat_id=chat_id,
            text=consent_text,
            reply_markup=consent_keyboard(),
        )
        return True

    # Step 4: OTP Verification & Account Activation
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
