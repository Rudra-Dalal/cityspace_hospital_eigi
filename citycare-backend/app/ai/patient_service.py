"""Grounded patient assistant integrating Clinic Handbook RAG and Personal Prescription RAG."""

from typing import Any, Dict, List, Tuple
from app.core.config import get_settings
from app.services.prescription_rag import retrieve_for_patient
from app.services.handbook_rag import retrieve_handbook_context
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SAFETY = "For medical advice, treatment changes, or emergencies, please consult your doctor or emergency services."


async def run_patient_chat(message: str, current_user: Dict[str, Any]) -> Tuple[str, List[str]]:
    patient_id = str(current_user["_id"])

    # Retrieve patient-scoped prescriptions
    prescription_records = await retrieve_for_patient(patient_id, message)

    # Retrieve general clinic handbook context
    handbook_chunks = await retrieve_handbook_context(message, limit=4)

    sources: List[str] = []
    if prescription_records:
        sources.append("Retrieved your prescription")

    for chunk in handbook_chunks:
        page = chunk.get("page")
        policy = chunk.get("policy")
        section = chunk.get("section", "")
        if policy:
            sources.append(f"Handbook Page {page} ({policy}: {section})")
        else:
            sources.append(f"Handbook Page {page} ({section})")

    if not prescription_records and not handbook_chunks:
        return f"I could not find prescription information or handbook details for that question. {_SAFETY}", []

    handbook_lines = []
    for c in handbook_chunks:
        page = c.get("page")
        policy = c.get("policy")
        sec = c.get("section")
        pol_str = f" ({policy})" if policy else ""
        handbook_lines.append(f"[Page {page}{pol_str} - Section: {sec}]\n{c.get('text')}")
    handbook_context = "\n\n".join(handbook_lines)

    patient_context = "\n\n".join(rec["text"] for rec in prescription_records)

    settings = get_settings()
    api_key = settings.gemini_api_key

    if not api_key or api_key.startswith("your-"):
        # Fallback response when Gemini API key is unconfigured
        res_parts = []
        if handbook_chunks:
            top_text = handbook_chunks[0]["text"]
            res_parts.append(f"According to the CityCare Clinic Patient Handbook:\n{top_text}")
        if prescription_records:
            res_parts.append(f"Prescription info:\n{prescription_records[0]['text']}")
        res_parts.append(f"Note: Gemini API key is not configured for full chat generation. {_SAFETY}")
        return "\n\n".join(res_parts), sources

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = f"""You are the official CityCare Clinic AI Assistant. Answer the user's question using the provided Handbook Context (for general clinic policies, fees, timings, services, and rules) and Patient Context (for personal prescription queries).

GROUNDING RULES:
1. Use HANDBOOK CONTEXT for general CityCare information. Treat it as the authoritative source for clinic policies and operational details.
2. Do not invent clinic fees, timings, policies, services, or rules.
3. If the handbook does not contain the answer to a general clinic question, clearly state that the handbook does not provide that information.
4. Use PATIENT CONTEXT only for answering questions about the authenticated patient's own prescriptions.
5. Never alter or reinterpret patient medication instructions, dosage, or frequency.
6. Do not fabricate sources or turn handbook information into a medical diagnosis.
7. If useful, reference the relevant policy code or page number.
8. Advise the patient to consult their doctor for any medical decisions or treatment changes.

HANDBOOK CONTEXT:
{handbook_context or "No relevant handbook context found."}

PATIENT CONTEXT:
{patient_context or "No relevant personal prescription context found."}

USER QUESTION:
{message}"""

        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        answer = (response.text or "").strip()
        if not answer:
            answer = f"I could not find prescription information or handbook details for that question. {_SAFETY}"
        return answer, sources
    except Exception as exc:
        logger.error("Error generating patient chat response: %s", exc)
        res_parts = []
        if handbook_chunks:
            top_text = handbook_chunks[0]["text"]
            res_parts.append(f"According to the CityCare Clinic Patient Handbook:\n{top_text}")
        if prescription_records:
            res_parts.append(f"Prescription info:\n{prescription_records[0]['text']}")
        if not res_parts:
            res_parts.append(f"I could not find prescription information or handbook details for that question. {_SAFETY}")
        return "\n\n".join(res_parts), sources

