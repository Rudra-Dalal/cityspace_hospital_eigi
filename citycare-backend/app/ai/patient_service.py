"""Grounded patient prescription assistant."""

from typing import Any, Dict, Optional, Tuple
from app.core.config import get_settings
from app.services.prescription_rag import retrieve_for_patient

_SAFETY = "I can only provide information contained in your prescriptions. For treatment changes or medical decisions, please contact your doctor."


async def run_patient_chat(message: str, current_user: Dict[str, Any]) -> Tuple[str, list[str]]:
    records = await retrieve_for_patient(str(current_user["_id"]), message)
    if not records:
        return "I could not find prescription information for that question. " + _SAFETY, []
    context = "\n\n".join(record["text"] for record in records)
    settings = get_settings()
    api_key = settings.gemini_api_key
    if not api_key or api_key.startswith("your-"):
        return "Your prescription information is available, but the chat service is not configured. " + _SAFETY, ["Retrieved your prescription"]
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = f"""You are a prescription information assistant. Answer ONLY from the patient-specific prescription context below. Do not invent facts, dosage, frequency, duration, or medical advice. If absent, say it is not available. End medical decision answers by advising the patient to consult their doctor.\n\nContext:\n{context}\n\nQuestion: {message}"""
        response = await client.aio.models.generate_content(model=settings.gemini_model, contents=prompt)
        answer = (response.text or "").strip()
        return (answer or "The information is not available in your prescription context. " + _SAFETY), ["Retrieved your prescription"]
    except Exception as exc:
        raise RuntimeError("Patient assistant unavailable") from exc
