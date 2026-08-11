"""Voice AI service connecting incoming phone calls to existing Handbook RAG and Gemini AI."""

from typing import Dict, List, Optional
from app.core.config import get_settings
from app.services.handbook_rag import retrieve_handbook_context
from app.voice.prompt import VOICE_SYSTEM_PROMPT
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Lightweight in-memory session store for active call conversations
_active_call_sessions: Dict[str, List[Dict[str, str]]] = {}


def get_call_session(call_sid: str) -> List[Dict[str, str]]:
    """Retrieve or initialize conversation history for an active call."""
    if call_sid not in _active_call_sessions:
        _active_call_sessions[call_sid] = []
    return _active_call_sessions[call_sid]


def clear_call_session(call_sid: str) -> None:
    """Clean up conversation history when call ends."""
    _active_call_sessions.pop(call_sid, None)


async def run_voice_chat(message: str, call_sid: str = "default") -> str:
    """
    Process a user's spoken transcript through existing Handbook RAG & Gemini.
    Maintains per-call multi-turn context without disclosing private patient data.
    """
    if not message or not message.strip():
        return "I didn't quite catch that. Could you please repeat your question?"

    # Check for private patient data requests (calls are unauthenticated)
    msg_lower = message.lower()
    patient_keywords = ["my prescription", "prescribed to me", "my medical record", "my medicine", "my diagnosis"]
    if any(kw in msg_lower for kw in patient_keywords):
        return "For privacy and security, personal prescription records can only be accessed by logging into your account on the CityCare website. I can help answer general questions about clinic hours, fees, and services."

    # Retrieve general clinic handbook context
    handbook_chunks = await retrieve_handbook_context(message, limit=4)
    handbook_context = "\n\n".join(
        f"[Section: {c.get('section')}]\n{c.get('text')}"
        for c in handbook_chunks
    )

    history = get_call_session(call_sid)
    history_str = "\n".join(
        f"User: {h['user']}\nAssistant: {h['assistant']}"
        for h in history[-3:]  # Retain last 3 turns
    )

    settings = get_settings()
    api_key = settings.gemini_api_key

    # Fallback if Gemini key is not configured
    if not api_key or api_key.startswith("your-"):
        if handbook_chunks:
            top_text = handbook_chunks[0]["text"]
            reply = f"According to the CityCare Clinic handbook: {top_text}"
        else:
            reply = "CityCare Clinic is open Monday to Saturday. For more details please visit our website at citycareclinic.in."
        history.append({"user": message, "assistant": reply})
        return reply

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""{VOICE_SYSTEM_PROMPT}

HANDBOOK CONTEXT:
{handbook_context or "No relevant handbook context found."}

CONVERSATION HISTORY:
{history_str or "No previous turns."}

CALLER QUESTION:
{message}"""

        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        answer = (response.text or "").strip()
        # Clean any accidental markdown for speech
        answer = answer.replace("*", "").replace("#", "").replace("`", "").strip()

        if not answer:
            answer = "I'm sorry, I couldn't find details on that in our clinic handbook. Please feel free to ask about our hours, fees, or services."

        history.append({"user": message, "assistant": answer})
        return answer

    except Exception as exc:
        logger.error("Error generating voice AI response: %s", exc)
        return "I am having trouble looking that up right now. Please hold or call back shortly."
