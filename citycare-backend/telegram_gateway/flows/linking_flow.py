"""Account linking flow for existing registered patients."""

import re
from typing import Any, Dict, Optional

from app.cruds import user_crud
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.keyboards import main_menu_keyboard
from telegram_gateway.models import TelegramFlowType, TelegramSession
from telegram_gateway.session_manager import SessionManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def start_linking_flow(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    patient: Optional[Dict[str, Any]],
) -> None:
    """Initiate existing account linking workflow."""
    if patient:
        p_name = escape_markdown(f"{patient.get('first_name')} {patient.get('last_name')}")
        p_email = escape_markdown(patient.get("email"))
        await adapter.send_message(
            chat_id=chat_id,
            text=f"ℹ️ *Already Linked*\n\nThis Telegram account is already linked to patient *{p_name}* \\({p_email}\\)\\.",
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return

    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.LINKING.value,
        flow_step="enter_identifier",
        flow_data={},
    )

    await adapter.send_message(
        chat_id=chat_id,
        text=(
            "🔗 *Link Existing Patient Account*\n\n"
            "Please enter your registered *email address* or *mobile number* \\(e\\.g\\. `patient@example.com` or `+919876543210`\\):"
        ),
    )


async def handle_linking_text_message(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    user_id: int,
    text: str,
) -> bool:
    """Handle text inputs during the account linking flow."""
    if session.current_flow != TelegramFlowType.LINKING.value:
        return False

    flow_step = session.flow_step
    flow_data = dict(session.flow_data or {})
    input_str = text.strip()

    # Step 1: User entered Email or Mobile
    if flow_step == "enter_identifier":
        user_record = None
        target_type = "email"

        if "@" in input_str:
            target_type = "email"
            user_record = await user_crud.get_user_by_email(input_str.lower())
        elif re.fullmatch(r"\+91[6-9]\d{9}", input_str) or re.fullmatch(r"[6-9]\d{9}", input_str):
            target_type = "mobile"
            norm_mobile = input_str if input_str.startswith("+91") else f"+91{input_str}"
            user_record = await user_crud.get_user_by_mobile(norm_mobile)
        else:
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Please enter a valid email address or 10-digit Indian mobile number with +91\\.",
            )
            return True

        if not user_record or user_record.get("is_active") is False:
            await adapter.send_message(
                chat_id=chat_id,
                text=(
                    "❌ *Account Not Found*\n\n"
                    "No active patient account was found matching those details\\. "
                    "If you are a new patient, please use /register to create an account\\."
                ),
                reply_markup=main_menu_keyboard(is_verified=False),
            )
            await SessionManager.clear_flow(session.session_key)
            return True

        patient_id = str(user_record["_id"])
        target_val = user_record.get("email") if target_type == "email" else user_record.get("mobile")

        # Issue 6-digit OTP
        issued = await IdentityManager.issue_otp(
            telegram_user_id=user_id,
            target_type=target_type,
            target_value=target_val,
            purpose="link_account",
            metadata={"patient_id": patient_id},
        )

        if not issued:
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ Could not send verification code at this time\\. Please try again later\\.",
            )
            await SessionManager.clear_flow(session.session_key)
            return True

        flow_data["patient_id"] = patient_id
        flow_data["target_type"] = target_type
        flow_data["target_value"] = target_val

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.LINKING.value,
            flow_step="enter_otp",
            flow_data=flow_data,
        )

        # Mask target for privacy
        masked = target_val[:3] + "..." + target_val[-4:] if len(target_val) > 7 else target_val
        masked_esc = escape_markdown(masked)

        dev_hint = ""
        if settings.telegram_otp_provider.lower().strip() == "dev":
            from telegram_gateway.otp_service import get_otp_delivery_service
            dev_svc = get_otp_delivery_service()
            if hasattr(dev_svc, "get_latest_otp"):
                dev_code = dev_svc.get_latest_otp(target_val)
                if dev_code:
                    dev_hint = f"\n\n🔑 *Dev Code:* `{dev_code}`"

        await adapter.send_message(
            chat_id=chat_id,
            text=(
                f"📩 *Verification Code Sent*\n\n"
                f"We sent a 6\\-digit verification code to `{masked_esc}`\\.{dev_hint}\n\n"
                f"Please enter the code to verify and link your account:"
            ),
        )
        return True

    # Step 2: User entered 6-digit OTP
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
            purpose="link_account",
        )

        if not is_valid:
            err_esc = escape_markdown(error_msg)
            await adapter.send_message(chat_id=chat_id, text=f"❌ {err_esc}")
            return True

        patient_id = meta.get("patient_id") if meta else flow_data.get("patient_id")
        if not patient_id:
            await adapter.send_message(chat_id=chat_id, text="Session error. Please restart /link.")
            await SessionManager.clear_flow(session.session_key)
            return True

        # Perform 1-to-1 link
        success, msg = await IdentityManager.link_patient(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            patient_id=patient_id,
        )

        if not success:
            msg_esc = escape_markdown(msg)
            await adapter.send_message(
                chat_id=chat_id,
                text=f"❌ *Linking Failed*\n\n{msg_esc}",
                reply_markup=main_menu_keyboard(is_verified=False),
            )
            await SessionManager.clear_flow(session.session_key)
            return True

        # Success: update session
        await SessionManager.set_patient_id(session.session_key, patient_id)
        await SessionManager.clear_flow(session.session_key)

        patient_user = await user_crud.get_user_by_id(patient_id)
        p_name = escape_markdown(f"{patient_user.get('first_name')} {patient_user.get('last_name')}" if patient_user else "Patient")

        await adapter.send_message(
            chat_id=chat_id,
            text=(
                f"✅ *Account Linked Successfully!*\n\n"
                f"Welcome back, *{p_name}*\\! You can now book appointments, view your appointment schedule, and access prescriptions directly in Telegram\\."
            ),
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return True

    return False
