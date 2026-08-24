"""Clinical & Policy AI assistant using Clinic Handbook RAG and Patient Prescription RAG."""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.ai.patient_service import run_patient_chat
from app.services.handbook_rag import retrieve_handbook_context
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.keyboards import main_menu_keyboard
from app.utils.logger import get_logger

logger = get_logger(__name__)

EMERGENCY_KEYWORDS = [
    r"\bchest\s*pain\b",
    r"\bheart\s*attack\b",
    r"\bshortness\s*of\s*breath\b",
    r"\bbreathing\s*(trouble|difficulty)\b",
    r"\bstroke\b",
    r"\bunconscious\b",
    r"\bsevere\s*bleeding\b",
    r"\bsuicid(e|al)\b",
    r"\bpoison(ing|ed)?\b",
    r"\banaphylaxis\b",
]

_EMERGENCY_ALERT = (
    "🚨 *CRITICAL EMERGENCY NOTICE*\n\n"
    "Your message mentions potential red\\-flag or emergency symptoms\\. "
    "If you or someone nearby is experiencing acute chest pain, severe breathing difficulty, sudden weakness, or loss of consciousness, "
    "*please contact emergency medical services immediately or visit the nearest hospital emergency department\\.*"
)


def _detect_emergency(text: str) -> bool:
    """Check text for acute red-flag emergency keywords."""
    lower = text.lower()
    for pattern in EMERGENCY_KEYWORDS:
        if re.search(pattern, lower):
            return True
    return False


async def handle_ai_health_chat(
    adapter: TelegramAdapter,
    chat_id: int,
    text: str,
    patient: Optional[Dict[str, Any]],
) -> None:
    """Process natural language query with Handbook RAG, Personal Prescription RAG, or Gemini."""
    query = text.strip()
    if not query:
        return

    # Check for acute emergency
    if _detect_emergency(query):
        await adapter.send_message(
            chat_id=chat_id,
            text=_EMERGENCY_ALERT,
            reply_markup=main_menu_keyboard(is_verified=bool(patient)),
        )
        return


    await adapter.send_chat_action(chat_id=chat_id, action="typing")

    if patient:
        # Verified patient: Grounded RAG across personal prescriptions + handbook
        try:
            answer, sources = await run_patient_chat(message=query, current_user=patient)
            ans_esc = escape_markdown(answer)

            sources_text = ""
            if sources:
                src_esc = "\n".join(f"• _{escape_markdown(s)}_" for s in sources)
                sources_text = f"\n\n📚 *Sources Referenced:*\n{src_esc}"

            reply_msg = f"{ans_esc}{sources_text}"
            await adapter.send_message(
                chat_id=chat_id,
                text=reply_msg,
                reply_markup=main_menu_keyboard(is_verified=True),
            )
        except Exception as exc:
            logger.error("Patient AI chat error: %s", exc)
            await adapter.send_message(
                chat_id=chat_id,
                text=(
                    "ℹ️ *CityCare Health Assistant*\n\n"
                    "I am currently unable to process complex medical questions\\. "
                    "For appointment booking, use /book\\. For emergencies, consult your doctor or emergency services\\."
                ),
                reply_markup=main_menu_keyboard(is_verified=True),
            )
    else:
        # Unverified user: Only Clinic Handbook RAG (policies, timings, fees, branch info)
        try:
            chunks = await retrieve_handbook_context(query=query, limit=3)
            if not chunks:
                await adapter.send_message(
                    chat_id=chat_id,
                    text=(
                        "ℹ️ *CityCare Clinic Information*\n\n"
                        "I could not find handbook details matching your question\\. "
                        "To book an appointment or view hospital services, please use /hospitals, /doctors, or /register\\."
                    ),
                    reply_markup=main_menu_keyboard(is_verified=False),
                )
                return

            info_parts = ["ℹ️ *CityCare Clinic Information:*\n"]
            for c in chunks:
                p_text = escape_markdown(c.get("text", ""))
                sec = escape_markdown(c.get("section", ""))
                info_parts.append(f"• *{sec}:*\n{p_text}\n")

            info_parts.append("_For personal prescriptions and medical records, please link your account with /link\\._")
            await adapter.send_message(
                chat_id=chat_id,
                text="\n".join(info_parts),
                reply_markup=main_menu_keyboard(is_verified=False),
            )
        except Exception as exc:
            logger.error("Handbook RAG query error: %s", exc)
            await adapter.send_message(
                chat_id=chat_id,
                text="ℹ️ To explore CityCare services and specialists, please use /hospitals or /doctors\\.",
                reply_markup=main_menu_keyboard(is_verified=False),
            )
