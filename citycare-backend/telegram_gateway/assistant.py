"""Conversational Assistant (Hermes Agent) for Telegram Patient Assistant.

Architecture:
    Telegram Router
         ↓
    ConversationalAssistant
         ↓
    Intent & Entity Extraction (Gemini + Deterministic Fallback)
         ↓
    Conversation State (MongoDB telegram_sessions)
         ↓
    Authorization & Clinical Validation (Strict Server-Side)
         ↓
    Existing Medihub Backend Services (Reused Deterministically)
         ↓
    MongoDB
         ↓
    Natural Conversational Response (with Optional Keyboard Shortcuts)
"""

import asyncio
from datetime import date as date_cls, datetime, timedelta, timezone
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import zoneinfo

from app.core.config import get_settings
from app.services.patient_discovery_service import (
    get_current_date_in_tz,
    validate_booking_date,
    list_active_hospitals,
    get_hospital_details,
    list_active_doctors,
    get_doctor_details,
    get_doctor_availability,
)
from app.services.patient_appointment_service import (
    book_patient_appointment,
    get_patient_appointments,
    cancel_patient_appointment,
    BookingError,
    SlotConflictError,
)
from app.services.patient_prescription_service import (
    get_patient_prescriptions,
    get_prescription_details,
)
from app.services.registration_service import register_patient
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.flows.chat_flow import _detect_emergency, _EMERGENCY_ALERT
from telegram_gateway.flows.prescriptions_flow import (
    show_latest_prescription_conversational,
    show_prescription_medicines_summary,
    show_patient_prescriptions,
)
from telegram_gateway.identity_manager import IdentityManager
from telegram_gateway.keyboards import (
    build_inline_keyboard,
    hospitals_keyboard,
    specializations_keyboard,
    doctors_keyboard,
    dates_keyboard,
    slots_keyboard,
    confirmation_keyboard,
    main_menu_keyboard,
    compact_menu_keyboard,
    single_action_keyboard,
    quick_shortcut_keyboard,
    registration_summary_keyboard,
    quick_departments_keyboard,
)
from telegram_gateway.conversation_policy import (
    ConversationMode,
    should_show_keyboard,
    clear_stale_keyboard,
    send_conversational_response,
)
from telegram_gateway.models import TelegramFlowType, TelegramSession
from telegram_gateway.session_manager import SessionManager
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Medical symptom to specialization map
SYMPTOM_SPECIALIZATION_MAP = [
    (r"\b(skin|rash|rashes|itching|itchy|acne|pimples?|eczema|psoriasis|mole|dermatolog(?:ist|y)s?)\b", "Dermatology"),
    (r"\b(chest\s*pain|heart|palpitation|palpitations|high\s*bp|blood\s*pressure|cardiolog(?:ist|y)s?)\b", "Cardiology"),
    (r"\b(tooth|teeth|dental|dentists?|toothache|gum|gums|cavity)\b", "Dental"),
    (r"\b(stomach|tummy|abdomen|abdominal|acidity|gas|indigestion|vomit(?:ing)?|nausea|diarrhea|loose\s*motion|gastroenterolog(?:ist|y)s?)\b", "Gastroenterology"),
    (r"\b(bone|joint|knee|knee\s*pain|back\s*pain|spine|fracture|sprain|orthopedic(?:s)?s?|ortho)\b", "Orthopedics"),
    (r"\b(child|baby|infant|kid|toddler|pediatric(?:ian|s)?s?)\b", "Pediatrics"),
    (r"\b(eye|eyes|vision|blurred\s*vision|cataract|ophthalmolog(?:ist|y)s?)\b", "Ophthalmology"),
    (r"\b(headache|migraine|dizziness|fainting|neurolog(?:ist|y)s?)\b", "Neurology"),
    (r"\b(ear|nose|throat|sinus|sinusitis|hearing|ent)\b", "ENT"),
    (r"\b(fever|cold|cough|flu|chills|weakness|fatigue|body\s*ache|general\s*(?:physicians?|doctors?|medicine)?)\b", "General Physician"),
]


def extract_registration_entities(text: str) -> Dict[str, str]:
    """Extract name, DOB, email, and mobile from natural text."""
    entities: Dict[str, str] = {}
    clean_text = text.strip()

    # 1. Email
    email_match = re.search(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b", clean_text)
    if email_match:
        entities["email"] = email_match.group(0).lower().strip()

    # 2. Indian Mobile
    mob_match = re.search(r"(?:\+91[\s\-]?)?[6-9]\d{9}", clean_text)
    if mob_match:
        raw_mob = re.sub(r"[\s\-]", "", mob_match.group(0))
        if not raw_mob.startswith("+91"):
            raw_mob = f"+91{raw_mob}"
        entities["mobile"] = raw_mob

    # 3. Date of birth
    dob_match = re.search(
        r"(?:dob\s*(?:is|:)?|born\s*(?:on)?|date\s*of\s*birth\s*(?:is|:)?)\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        clean_text,
        re.IGNORECASE,
    )
    if dob_match:
        entities["dob"] = dob_match.group(1).strip()
    else:
        # Fallback date pattern if not used as email or mobile
        date_pattern = re.search(r"\b([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{4})\b", clean_text)
        if date_pattern:
            entities["dob"] = date_pattern.group(1).strip()

    # 4. Name extraction
    name_match = re.search(
        r"(?:my\s*name\s*is|i\s*am|name\s*(?:is|:)?|register\s*(?:me\s*)?(?:as|:)?)\s+([A-Za-z]{2,25}(?:\s+[A-Za-z]{2,25})+)",
        clean_text,
        re.IGNORECASE,
    )
    stop_words = {"and", "my", "is", "dob", "born", "date", "of", "birth", "email", "phone", "mobile", "the", "register", "me"}
    if name_match:
        raw_name = name_match.group(1).strip()
        clean_parts = [p for p in raw_name.split() if p.lower() not in stop_words]
        if len(clean_parts) >= 2:
            entities["first_name"] = clean_parts[0].strip()
            entities["last_name"] = clean_parts[1].strip()
            entities["full_name"] = f"{entities['first_name']} {entities['last_name']}"
    else:
        # Check leading name before comma, keyword or email
        lead_match = re.match(
            r"^([A-Z][a-z]{1,25}(?:\s+[A-Z][a-z]{1,25})+)(?:,|\s+dob|\s+born|\s+email|\s+phone|\s+mobile|$)",
            clean_text,
            re.IGNORECASE,
        )
        if lead_match:
            raw_name = lead_match.group(1).strip()
            clean_parts = [p for p in raw_name.split() if p.lower() not in stop_words]
            if len(clean_parts) >= 2:
                entities["first_name"] = clean_parts[0].strip()
                entities["last_name"] = clean_parts[1].strip()
                entities["full_name"] = f"{entities['first_name']} {entities['last_name']}"
        elif not entities.get("email") and not entities.get("dob") and not entities.get("mobile"):
            # Standalone name input (e.g. "Rudra Dalal")
            parts = clean_text.split(None, 1)
            if len(parts) == 2 and all(p.isalpha() for p in parts):
                entities["first_name"] = parts[0].strip()
                entities["last_name"] = parts[1].strip()
                entities["full_name"] = clean_text

    return entities


def parse_relative_date(date_text: str, tz_name: str = "Asia/Kolkata") -> Optional[str]:
    """Parse relative date words or standard date formats to ISO YYYY-MM-DD."""
    lower = date_text.strip().lower()
    today = get_current_date_in_tz(tz_name)

    if re.search(r"\b(day after tomorrow|day after tmrw)\b", lower):
        return (today + timedelta(days=2)).isoformat()
    if re.search(r"\b(tomorrow|tomorrows|tmrw)\b", lower):
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\b(today|todays)\b", lower):
        return today.isoformat()

    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for idx, w in enumerate(weekdays):
        if re.search(rf"\b{w}\b", lower):
            current_weekday = today.weekday()  # Monday is 0, Sunday is 6
            target_weekday = idx
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next occurrence
            return (today + timedelta(days=days_ahead)).isoformat()

    # Regex for YYYY-MM-DD
    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", lower)
    if iso_match:
        return iso_match.group(1)

    # Regex for DD/MM/YYYY or DD-MM-YYYY
    dmy_match = re.search(r"\b(\d{1,2})[\/\-](\d{1,2})[\/\-](20\d{2})\b", lower)
    if dmy_match:
        day, month, year = int(dmy_match.group(1)), int(dmy_match.group(2)), int(dmy_match.group(3))
        try:
            return date_cls(year, month, day).isoformat()
        except ValueError:
            pass

    return None


def parse_time_slot(time_text: str) -> Optional[str]:
    """Parse natural time string to standard slot format, e.g. '10:30 AM'."""
    lower = time_text.strip().lower()

    # Require either a colon (10:30) or am/pm (10 am) or "at \d"
    match = re.search(r"(?:at\s+)?\b([0-1]?[0-9]|2[0-3]):([0-5][0-9])\s*(am|pm)?\b", lower)
    if not match:
        match = re.search(r"\b([1-9]|1[0-2])\s*(am|pm)\b", lower)
        if not match:
            match = re.search(r"(?:at\s+)\b([1-9]|1[0-2])(?:\s*o'?clock)?\b", lower)
            if not match:
                return None
            hour = int(match.group(1))
            minute = 0
            meridiem = None
        else:
            hour = int(match.group(1))
            minute = 0
            meridiem = match.group(2)
    else:
        hour = int(match.group(1))
        minute = int(match.group(2))
        meridiem = match.group(3)

    if meridiem:
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
    else:
        if 1 <= hour <= 6:
            hour += 12  # e.g. "3" or "3:00" -> 15:00

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None

    display_hour = hour % 12
    display_hour = 12 if display_hour == 0 else display_hour
    display_meridiem = "PM" if hour >= 12 else "AM"
    return f"{display_hour:02d}:{minute:02d} {display_meridiem}"


def parse_time_preference(text: str) -> Optional[str]:
    """Extract general time of day preference (morning, afternoon, evening)."""
    lower = text.strip().lower()
    if re.search(r"\b(morning|am)\b", lower):
        return "morning"
    if re.search(r"\b(afternoon)\b", lower):
        return "afternoon"
    if re.search(r"\b(evening|night)\b", lower):
        return "evening"
    return None


def resolve_doctor_reference(
    query: str,
    presented_doctors: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Resolve ordinal or contextual doctor reference from presented doctors list.
    Examples:
      - 'the first one', 'first doctor', '1st one', 'first', 'earlier one', 'that doctor' -> presented_doctors[0]
      - 'the second doctor', 'second one', '2nd one', 'second' -> presented_doctors[1]
      - 'the third doctor', 'third one', '3rd one', 'third' -> presented_doctors[2]
      - 'the last doctor', 'last one', 'the last one' -> presented_doctors[-1]
      - 'Sharma', 'Dr Sharma', 'Dr. Sharma', 'Mehta' -> matching doctor by surname or name
    """
    if not presented_doctors:
        return None

    clean = query.strip().lower()

    # 1. Check ordinal references
    if re.search(r"\b(first|1st|earlier|earliest)\b", clean):
        return presented_doctors[0]
    if re.search(r"\b(second|2nd)\b", clean) and len(presented_doctors) > 1:
        return presented_doctors[1]
    if re.search(r"\b(third|3rd)\b", clean) and len(presented_doctors) > 2:
        return presented_doctors[2]
    if re.search(r"\b(fourth|4th)\b", clean) and len(presented_doctors) > 3:
        return presented_doctors[3]
    if re.search(r"\b(last|latest)\b", clean):
        return presented_doctors[-1]
    if re.search(r"\b(that doctor|that one|this one)\b", clean) and len(presented_doctors) == 1:
        return presented_doctors[0]

    # 2. Check surname / name matches against presented doctors
    for doc in presented_doctors:
        first = (doc.get("first_name") or "").lower()
        last = (doc.get("last_name") or "").lower()
        doc_name = (doc.get("name") or "").lower()

        if last and last in clean:
            return doc
        if first and len(first) > 2 and first in clean:
            return doc
        if doc_name and doc_name in clean:
            return doc

    return None


def resolve_slot_reference(
    query: str,
    presented_slots: List[str],
) -> Optional[str]:
    """
    Resolve ordinal, time-of-day, or partial time reference from presented slots.
    Examples:
      - 'the first slot', 'the first one', 'first slot', 'first', 'earliest', 'earliest slot' -> presented_slots[0]
      - 'the second slot', 'second', '2nd slot' -> presented_slots[1]
      - 'the third slot', 'third', '3rd slot' -> presented_slots[2]
      - 'the last slot', 'last', 'latest' -> presented_slots[-1]
      - 'morning', 'the morning slot' -> first slot with 'AM'
      - 'afternoon' -> first slot with 'PM' before 17:00
      - 'evening' -> first slot after 17:00
      - '10:30', '10:30 AM', '11' -> matching slot string
    """
    if not presented_slots:
        return None

    clean = query.strip().lower()

    # 1. Check ordinal references
    if re.search(r"\b(first|1st|earliest)\b", clean):
        return presented_slots[0]
    if re.search(r"\b(second|2nd)\b", clean) and len(presented_slots) > 1:
        return presented_slots[1]
    if re.search(r"\b(third|3rd)\b", clean) and len(presented_slots) > 2:
        return presented_slots[2]
    if re.search(r"\b(fourth|4th)\b", clean) and len(presented_slots) > 3:
        return presented_slots[3]
    if re.search(r"\b(last|latest)\b", clean):
        return presented_slots[-1]

    # 2. Check time of day preferences
    if re.search(r"\b(morning|am)\b", clean):
        morning_slots = [s for s in presented_slots if "am" in s.lower() or int(s.split(":")[0]) < 12]
        if morning_slots:
            return morning_slots[0]

    if re.search(r"\b(afternoon)\b", clean):
        afternoon_slots = [
            s for s in presented_slots
            if "pm" in s.lower() and (int(s.split(":")[0]) == 12 or int(s.split(":")[0]) < 5)
        ]
        if afternoon_slots:
            return afternoon_slots[0]

    if re.search(r"\b(evening)\b", clean):
        evening_slots = [
            s for s in presented_slots
            if "pm" in s.lower() and (int(s.split(":")[0]) >= 5 and int(s.split(":")[0]) != 12)
        ]
        if evening_slots:
            return evening_slots[0]

    # 3. Direct or normalized time match
    clean_time = clean.replace(" ", "").replace(".", "")
    for slot in presented_slots:
        norm_slot = slot.lower().replace(" ", "").replace(".", "")
        if clean_time in norm_slot or norm_slot in clean_time:
            return slot
        time_part = slot.split()[0].lower()
        if time_part == clean or clean.startswith(time_part):
            return slot

    # 4. Try parse_time_slot
    parsed = parse_time_slot(query)
    if parsed:
        for slot in presented_slots:
            if slot.lower().replace(" ", "") == parsed.lower().replace(" ", ""):
                return slot

    return None


class ConversationalAssistant:
    """Master conversational Hermes Agent for CityCare Hospital Telegram Assistant."""

    def __init__(self, adapter: Optional[TelegramAdapter] = None):
        self.adapter = adapter or TelegramAdapter()

    async def handle_message(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
        from_user: Dict[str, Any],
    ) -> None:
        """Process incoming natural language query with full context retention and graceful recovery."""
        query = text.strip()
        if not query:
            return

        # Clear stale inline keyboard from prior turns
        await clear_stale_keyboard(self.adapter, chat_id, session)

        # 1. Critical Emergency Check
        if _detect_emergency(query):
            await self.adapter.send_message(
                chat_id=chat_id,
                text=_EMERGENCY_ALERT,
            )
            return

        # 2. Extract Intent & Entities (Hybrid Gemini + Deterministic Fallback)
        parsed = await self._classify_intent_and_entities(query, session, patient)
        intent = parsed.get("intent", "general_chat")
        entities = parsed.get("entities", {})

        logger.info("Conversational query: '%s' -> intent: %s, entities: %s", query, intent, entities)

        # 3. Global Workflow Pivot / Reset Handling
        if intent == "cancel_flow":
            await SessionManager.clear_flow(session.session_key)
            await self.adapter.send_message(
                chat_id=chat_id,
                text="No problem\\. I've cancelled that request\\. What would you like to do instead?",
            )
            return

        if intent == "change_mind_or_switch":
            await self._handle_context_switch(chat_id, session, patient, query, entities)
            return

        if intent == "symptom_intake_request":
            await self._handle_symptom_intake(chat_id, session, patient)
            return

        if intent == "ask_doctor_preference":
            await self._handle_ask_doctor_preference(chat_id, session)
            return

        # 4. Active Workflow Dispatches
        if session.current_flow == TelegramFlowType.REGISTRATION.value or intent == "register_patient":
            await self._handle_registration_flow(chat_id, user_id, session, patient, query, entities, from_user)
            return

        if intent == "view_medicines":
            await show_prescription_medicines_summary(self.adapter, chat_id, patient)
            return

        if intent == "view_prescriptions":
            await show_latest_prescription_conversational(self.adapter, chat_id, patient)
            return

        if intent == "view_appointments":
            await self._handle_view_appointments(chat_id, patient, session=session)
            return

        if intent == "cancel_appointment":
            await self._handle_cancel_appointment(chat_id, patient, entities, query)
            return

        if intent == "hospital_info":
            await self._handle_hospital_info(chat_id, entities)
            return

        if intent == "help":
            await self._handle_help(chat_id, patient, session=session)
            return

        if intent == "greeting":
            await self._handle_greeting(chat_id, patient, from_user, session=session)
            return

        if intent == "symptom_discussion":
            await self._handle_symptom_discussion(chat_id, session, patient, query, entities)
            return

        if intent in ("find_doctor", "check_availability"):
            await self._handle_doctor_discovery(chat_id, session, patient, query, entities)
            return

        if intent == "book_appointment" or session.current_flow == TelegramFlowType.BOOKING.value:
            await self._handle_appointment_booking(chat_id, session, patient, query, entities)
            return

        # 5. Fallback: Contextual Follow-up or General Hospital Assistant
        await self._handle_general_fallback(chat_id, session, patient, query, entities)

    async def _classify_intent_and_entities(
        self,
        text: str,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Hybrid intent and entity extraction: Gemini structured output with deterministic fallback."""
        settings = get_settings()
        api_key = settings.gemini_api_key

        # Try Gemini Structured Extraction if configured
        if api_key and not api_key.startswith("your-"):
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                prompt = f"""You are the NLU parser for CityCare Hospital's Patient Assistant.
Parse the user's message and return ONLY a single valid JSON object.

USER MESSAGE: "{text}"
CURRENT FLOW: "{session.current_flow}"
FLOW STEP: "{session.flow_step}"
PATIENT AUTHENTICATED: {bool(patient)}

POSSIBLE INTENTS:
- "greeting": user says hi, hello, good morning
- "symptom_intake_request": user asks to describe or explain symptoms first (e.g. "can I tell you my symptoms first?")
- "symptom_discussion": user describes a symptom or health concern (e.g. skin rash, tooth pain, headache)
- "ask_doctor_preference": user wants a doctor generally without specifics (e.g. "I need a doctor", "find me a doctor")
- "find_doctor": user wants to find, see, or list doctors or specialists
- "check_availability": user asks for doctor or department availability on a day
- "book_appointment": user wants to book, schedule, or reserve an appointment slot
- "cancel_appointment": user wants to cancel a booked appointment
- "view_appointments": user asks to view or see their scheduled appointments
- "view_prescriptions": user asks to see or download their prescriptions
- "view_medicines": user asks specifically what medicines or medications were prescribed
- "hospital_info": user asks about hospital branches, facilities, hours, services, location
- "register_patient": user asks to register or sign up as a patient
- "change_mind_or_switch": user says "actually I want a different doctor", "change doctor", "let's change date", "actually Friday"
- "cancel_flow": user says "I changed my mind", "cancel that", "forget it", "never mind", "start over"
- "confirm_action": user says "yes", "confirm", "proceed", "looks good", "correct", "book it"
- "help": user asks for help or commands
- "general_chat": any other clinic query

Extract entities where found:
- specialization (e.g. "Cardiology", "Dermatology", "Dental", "General Physician")
- doctor_name (e.g. "Dr Sharma", "Ananya Sharma")
- date (e.g. "tomorrow", "today", "Monday", "YYYY-MM-DD")
- slot (e.g. "10:30 AM", "11:00")
- reason (e.g. "skin rash", "routine checkup")
- patient_name, dob, email, mobile

OUTPUT FORMAT:
{{"intent": "<intent>", "entities": {{"specialization": null, "doctor_name": null, "date": null, "slot": null, "reason": null, "patient_name": null, "dob": null, "email": null, "mobile": null}}}}"""

                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=settings.gemini_model,
                        contents=prompt,
                    ),
                    timeout=3.5,
                )
                raw_output = (response.text or "").strip()
                # Remove markdown fences if returned
                if raw_output.startswith("```"):
                    raw_output = re.sub(r"^```(?:json)?\n|\n```$", "", raw_output).strip()
                parsed = json.loads(raw_output)
                if isinstance(parsed, dict) and "intent" in parsed:
                    # Sanitize entities
                    entities = parsed.get("entities") or {}
                    return {"intent": parsed["intent"], "entities": entities}
            except Exception as exc:
                logger.debug("Gemini intent extraction fallback triggered: %s", exc)

        # Fallback to Deterministic Extractor
        return self._deterministic_extract(text, session)

    def _deterministic_extract(self, text: str, session: TelegramSession) -> Dict[str, Any]:
        """Robust deterministic rule, regex, and keyword intent classifier."""
        lower = text.strip().lower()
        entities: Dict[str, Any] = {}

        # Check for cancel or change of mind
        if re.search(r"\b(changed my mind|forget (it|that)|nevermind|never mind|start over|cancel that)\b", lower):
            return {"intent": "cancel_flow", "entities": {}}

        if re.search(r"\b(different doctor|another doctor|change doctor|switch doctor|different specialist|someone else|actually,? someone else)\b", lower):
            return {"intent": "change_mind_or_switch", "entities": {"switch": "doctor"}}

        if re.search(r"\b(change\s*(?:the\s*)?date|different\s*date|another\s*date|actually\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today))\b", lower):
            return {"intent": "change_mind_or_switch", "entities": {"switch": "date"}}

        if re.search(r"^\b(cancel|reset|stop)\b$", lower):
            return {"intent": "cancel_flow", "entities": {}}

        # Symptom Intake Request (User asks to describe symptoms before choosing doctor)
        if (
            re.search(r"\b(can i|may i|i want to|let me|should i|could i)\b.*\b(symptom|symptoms|explain|describe|what'?s wrong|feeling)\b", lower)
            or re.search(r"\b(tell|explain|describe|share)\b.*\b(symptom|symptoms|what'?s wrong|how i feel|what i am feeling)\b", lower)
            or re.search(r"\bsymptoms?\s+first\b", lower)
        ):
            return {"intent": "symptom_intake_request", "entities": {}}

        # Help
        if re.search(r"^\b(help|guide|instructions)\b", lower):
            return {"intent": "help", "entities": {}}

        # Greeting
        if re.search(r"^\b(hi|hello|hey|greetings|good\s*(morning|afternoon|evening))\b", lower):
            return {"intent": "greeting", "entities": {}}

        # Prescriptions & Medicines
        if re.search(r"\b(medicine|medicines|medication|tablets?|pills?)\b", lower) and re.search(r"\b(prescribe|prescribed|prescriptions?|my|doctor)\b", lower):
            return {"intent": "view_medicines", "entities": {}}

        if re.search(r"\b(prescriptions?|prescription|rx|medical\s*records?)\b", lower):
            return {"intent": "view_prescriptions", "entities": {}}

        # Appointments
        if re.search(r"\b(cancel\s*(?:my\s*)?appointment)\b", lower):
            return {"intent": "cancel_appointment", "entities": {}}

        if re.search(r"\b(my\s*appointments?|show\s*(?:my\s*)?appointments?|view\s*appointments?|upcoming\s*appointments?)\b", lower):
            return {"intent": "view_appointments", "entities": {}}

        # Registration
        if (
            re.search(r"\b(register|sign\s*up|new\s*patient|create\s*profile|create\s*account|my\s*name\s*is|dob\s*(?:is|:)?|date\s*of\s*birth)\b", lower)
            or session.current_flow == TelegramFlowType.REGISTRATION.value
        ):
            reg_entities = extract_registration_entities(text)
            if reg_entities:
                return {"intent": "register_patient", "entities": reg_entities}
            elif re.search(r"\b(register|sign\s*up|new\s*patient|create\s*profile|create\s*account)\b", lower):
                return {"intent": "register_patient", "entities": {}}

        # Extract Date & Slot & Time preference
        parsed_date = parse_relative_date(text)
        if parsed_date:
            entities["date"] = parsed_date

        parsed_slot = parse_time_slot(text)
        if parsed_slot:
            entities["slot"] = parsed_slot

        time_pref = parse_time_preference(text)
        if time_pref:
            entities["time_preference"] = time_pref

        # Confirmation (only if NOT containing date/slot specifications or if in confirm_booking step)
        has_date_spec = bool(parsed_date)
        has_slot_spec = bool(parsed_slot)
        if session.flow_step == "confirm_booking" or (not has_date_spec and not has_slot_spec):
            if re.search(r"^\b(yes|confirm|proceed|looks good|correct|agree|i agree|book it|sure|go ahead|book)\b", lower):
                return {"intent": "confirm_action", "entities": {}}

        # Hospital Facilities
        if re.search(r"\b(facilities|facility|branches?|hospital\s*info|location|locations?|address)\b", lower):
            return {"intent": "hospital_info", "entities": {}}

        # Extract Doctor Name (e.g. "Dr. Sharma", "Dr Sharma", "Sharma", "Mehta")
        doc_match = re.search(r"(?:dr\.?|doctor)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", text, re.IGNORECASE)
        if doc_match:
            entities["doctor_name"] = doc_match.group(1).strip()
        elif re.search(r"\b(sharma|mehta|kulkarni|patel|gupta|verma)\b", lower):
            surname_match = re.search(r"\b(sharma|mehta|kulkarni|patel|gupta|verma)\b", lower)
            if surname_match:
                entities["doctor_name"] = surname_match.group(1).capitalize()

        # Extract Specialization / Symptoms
        for pattern, spec in SYMPTOM_SPECIALIZATION_MAP:
            if re.search(pattern, lower):
                entities["specialization"] = spec
                # Only treat as symptoms if not a search query like "find dermatologists"
                is_search_query = bool(re.search(r"\b(find|show|list|available|doctors?|specialists?|who are|which)\b", lower))
                if not is_search_query:
                    entities["symptoms"] = text
                break

        # Check for Open-Ended Doctor Request (e.g. "I need a doctor", "I want to see a doctor", "find me a doctor")
        # When NO doctor name, NO specialization, NO symptoms, and NO date were detected
        if (
            re.search(r"^\b(i\s*need\s*a\s*doctor|i\s*want\s*a\s*doctor|find\s*me\s*a\s*doctor|i\s*need\s*medical\s*help|need\s*a\s*doctor|want\s*a\s*doctor|see\s*a\s*doctor)\b", lower)
            and not entities.get("doctor_name")
            and not entities.get("specialization")
            and not entities.get("symptoms")
            and not entities.get("date")
        ):
            return {"intent": "ask_doctor_preference", "entities": {}}

        # If user is awaiting symptoms description, treat input as symptoms
        if session.flow_data.get("awaiting_symptoms"):
            entities["symptoms"] = text
            if not entities.get("specialization"):
                entities["specialization"] = "General Physician"
            return {"intent": "symptom_discussion", "entities": entities}

        # Symptom discussion
        if "symptoms" in entities and not ("book" in lower or "appointment" in lower):
            return {"intent": "symptom_discussion", "entities": entities}

        # Booking intent indicators
        if re.search(r"\b(book|appointment|schedule|consultation)\b", lower):
            return {"intent": "book_appointment", "entities": entities}

        # If date or slot or doctor provided and session already has specialization or active booking
        if entities.get("date") and (session.flow_data.get("specialization") or session.flow_data.get("doctor_id") or session.flow_step in ("symptom_followup", "select_doctor", "select_date")):
            if not entities.get("specialization") and session.flow_data.get("specialization"):
                entities["specialization"] = session.flow_data.get("specialization")
            return {"intent": "find_doctor", "entities": entities}

        # Find doctor
        if (
            re.search(r"\b(find|show|list|available|cardiologists?|dermatologists?|physicians?|doctors?|dr\.?|specialists?|want|need|see)\b", lower)
            or entities.get("doctor_name")
            or entities.get("specialization")
        ):
            return {"intent": "find_doctor", "entities": entities}

        # In-flight booking flow checks
        if session.current_flow == TelegramFlowType.BOOKING.value:
            if parsed_slot or parsed_date or entities.get("doctor_name") or entities.get("time_preference"):
                return {"intent": "book_appointment", "entities": entities}

        return {"intent": "general_chat", "entities": entities}

    async def _handle_greeting(
        self,
        chat_id: int,
        patient: Optional[Dict[str, Any]],
        from_user: Dict[str, Any],
        session: Optional[TelegramSession] = None,
    ) -> None:
        """Friendly natural greeting acknowledging patient status."""
        name = from_user.get("first_name", "there")
        if patient:
            p_name = escape_markdown(f"{patient.get('first_name', name)}")
            msg = f"""👋 *Hello {p_name}, welcome back to CityCare\\!*

I am your personal hospital assistant\\. How can I help you today?

You can:
• Search for specialists or explore hospital departments
• Book or check your doctor appointments
• View your medical prescriptions and dosages
• Inquire about hospital branches and facilities"""
        else:
            msg = f"""👋 *Hello {escape_markdown(name)}, welcome to CityCare Hospital\\!*

I am your hospital assistant\\. How can I help you today?

You can:
• Find specialist doctors and check available timings
• Describe your symptoms to find the right department
• Book an appointment or register as a patient
• Explore our clinic locations and facilities"""

        await send_conversational_response(
            adapter=self.adapter,
            chat_id=chat_id,
            text=msg,
            session=session,
            reply_markup=compact_menu_keyboard(is_verified=bool(patient)),
        )

    async def _handle_symptom_intake(
        self,
        chat_id: int,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
    ) -> None:
        """Invites patient to describe symptoms in natural words without buttons."""
        flow_data = dict(session.flow_data or {})
        flow_data["awaiting_symptoms"] = True
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="awaiting_symptoms",
            flow_data=flow_data,
        )
        await self.adapter.send_message(
            chat_id=chat_id,
            text="Absolutely\\. Tell me what's been bothering you\\. You can describe your symptoms in your own words, and I'll help you find an appropriate department or specialist\\.",
        )

    async def _handle_ask_doctor_preference(
        self,
        chat_id: int,
        session: TelegramSession,
    ) -> None:
        """Conversational clarification for open-ended 'I need a doctor'."""
        flow_data = dict(session.flow_data or {})
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="awaiting_doctor_or_symptoms",
            flow_data=flow_data,
        )
        await self.adapter.send_message(
            chat_id=chat_id,
            text="Of course\\. What would you like help with? You can describe what's bothering you, or tell me if you already have a specialist or doctor in mind\\.",
        )

    async def _handle_symptom_discussion(
        self,
        chat_id: int,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
        query: str,
        entities: Dict[str, Any],
    ) -> None:
        """Symptom exploration: empathize, safety guidance, map to department without diagnosing."""
        spec = entities.get("specialization") or session.flow_data.get("specialization") or "General Physician"

        # Update conversation state with specialization
        flow_data = dict(session.flow_data or {})
        flow_data["specialization"] = spec
        flow_data["symptoms"] = query
        flow_data.pop("awaiting_symptoms", None)
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="symptom_followup",
            flow_data=flow_data,
        )

        spec_esc = escape_markdown(spec)
        spec_plural = escape_markdown(f"{spec.lower()} specialists" if not spec.endswith("s") else f"{spec.lower()} doctors")

        reply = (
            f"Thanks for explaining that\\. Based on what you've described, *{spec_esc}* may be a relevant department to explore\\. "
            "I can't diagnose the condition, but I can help you find an appropriate specialist\\.\n\n"
            f"Would you like me to check available {spec_plural}?"
        )

        # Send conversational response with optional single action button
        await send_conversational_response(
            adapter=self.adapter,
            chat_id=chat_id,
            text=reply,
            session=session,
            reply_markup=single_action_keyboard(f"🔍 Find a {spec}", f"nav:spec:{spec}"),
        )

    async def _handle_doctor_discovery(
        self,
        chat_id: int,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
        query: str,
        entities: Dict[str, Any],
    ) -> None:
        """Find active doctors by specialization, name, or date availability."""
        spec = entities.get("specialization") or session.flow_data.get("specialization")
        doc_query = entities.get("doctor_name")
        target_date = entities.get("date") or session.flow_data.get("date")
        time_pref = entities.get("time_preference") or session.flow_data.get("time_preference")

        # 1. If no spec, no doctor, and no date: Ask intelligent follow-up without keyboard
        if not spec and not doc_query and not target_date:
            await self.adapter.send_message(
                chat_id=chat_id,
                text="Of course\\. What would you like help with? You can describe what's bothering you, or tell me if you already have a specialist or doctor in mind\\.",
            )
            return

        # 2. Query active doctors
        doctors = await list_active_doctors(specialization=spec)

        if doc_query:
            # Filter by doctor name partial match
            matched = [
                d for d in doctors
                if doc_query.lower() in f"{d.get('first_name', '')} {d.get('last_name', '')}".lower()
            ]
            if not matched:
                # Search across all doctors regardless of spec
                all_docs = await list_active_doctors()
                matched = [
                    d for d in all_docs
                    if doc_query.lower() in f"{d.get('first_name', '')} {d.get('last_name', '')}".lower()
                ]
            doctors = matched

        if not doctors:
            spec_str = f" in *{escape_markdown(spec)}*" if spec else ""
            await self.adapter.send_message(
                chat_id=chat_id,
                text=f"I couldn't find active specialists{spec_str}\\. Would you like to view our departments or explore other hospital branches?",
            )
            return

        # 3. If target date is specified, check real-time availability
        if target_date:
            available_doctors = []
            for d in doctors:
                avail = await get_doctor_availability(d["id"], target_date)
                if avail.get("is_available") and avail.get("available_slots"):
                    d_copy = dict(d)
                    d_copy["available_slots"] = avail["available_slots"]
                    available_doctors.append(d_copy)

            date_esc = escape_markdown(target_date)
            spec_name = spec or (doctors[0].get("specialization") if doctors else "Specialist")
            spec_esc = escape_markdown(spec_name)

            if not available_doctors:
                await self.adapter.send_message(
                    chat_id=chat_id,
                    text=f"None of our *{spec_esc}* doctors have open slots on *{date_esc}*\\. Would you like to check another date?",
                )
                return

            # Save state including presented_doctors
            flow_data = dict(session.flow_data or {})
            if spec:
                flow_data["specialization"] = spec
            flow_data["date"] = target_date
            if time_pref:
                flow_data["time_preference"] = time_pref

            flow_data["presented_doctors"] = [
                {
                    "id": d["id"],
                    "name": f"Dr. {d.get('first_name')} {d.get('last_name')}",
                    "first_name": d.get("first_name"),
                    "last_name": d.get("last_name"),
                    "specialization": d.get("specialization"),
                    "hospital_id": d.get("hospital_id"),
                    "hospital_name": d.get("hospital_name") or "Central Branch",
                    "available_slots": d.get("available_slots", []),
                }
                for d in available_doctors[:6]
            ]

            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="select_doctor",
                flow_data=flow_data,
            )

            lines = [f"I found a few *{spec_esc}* doctors who may work for you on *{date_esc}*:\n"]
            for idx, d in enumerate(available_doctors[:6], 1):
                name = escape_markdown(f"Dr. {d.get('first_name')} {d.get('last_name')}")
                hosp = escape_markdown(d.get("hospital_name") or "Central Branch")
                slots_list = d.get("available_slots", [])
                if time_pref == "morning":
                    m_slots = [s for s in slots_list if "am" in s.lower() or int(s.split(":")[0]) < 12]
                    display_slots = m_slots[:3] if m_slots else slots_list[:3]
                elif time_pref in ("afternoon", "evening"):
                    p_slots = [s for s in slots_list if "pm" in s.lower()]
                    display_slots = p_slots[:3] if p_slots else slots_list[:3]
                else:
                    display_slots = slots_list[:3]
                slots_str = escape_markdown(", ".join(display_slots)) if display_slots else "Available"
                lines.append(f"{idx}\\. *{name}*\n   🏥 {hosp}\n   ⏰ {slots_str}\n")

            lines.append("Which doctor would you prefer?")

            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text="\n".join(lines),
                session=session,
                reply_markup=doctors_keyboard(available_doctors[:6]),
            )
            return

        # 4. No specific date: list matching doctors with general working days
        spec_label = f" *{escape_markdown(spec)}*" if spec else ""
        lines = [f"Here are the available{spec_label} specialists at CityCare:\n"]
        for idx, d in enumerate(doctors[:6], 1):
            name = escape_markdown(f"Dr. {d.get('first_name')} {d.get('last_name')}")
            hosp = escape_markdown(d.get("hospital_name") or "Central Branch")
            qual = escape_markdown(d.get("qualification", "MD"))
            days = ", ".join(d.get("available_days", [])[:3])
            lines.append(f"{idx}\\. *{name}* — {qual}\n   🏥 {hosp} | 📅 Days: {escape_markdown(days)}")

        lines.append("\nWhich doctor or day would you prefer?")

        # Save specialization and presented_doctors in state
        flow_data = dict(session.flow_data or {})
        if spec:
            flow_data["specialization"] = spec
        flow_data["presented_doctors"] = [
            {
                "id": d["id"],
                "name": f"Dr. {d.get('first_name')} {d.get('last_name')}",
                "first_name": d.get("first_name"),
                "last_name": d.get("last_name"),
                "specialization": d.get("specialization"),
                "hospital_id": d.get("hospital_id"),
                "hospital_name": d.get("hospital_name") or "Central Branch",
            }
            for d in doctors[:6]
        ]
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="select_doctor",
            flow_data=flow_data,
        )

        await send_conversational_response(
            adapter=self.adapter,
            chat_id=chat_id,
            text="\n".join(lines),
            session=session,
            reply_markup=doctors_keyboard(doctors[:6]),
        )

    async def _handle_appointment_booking(
        self,
        chat_id: int,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
        query: str,
        entities: Dict[str, Any],
    ) -> None:
        """Multi-turn conversational booking: doctors, dates, slots, reason, and confirmation."""
        flow_data = dict(session.flow_data or {})

        # Merge extracted entities into session state
        if entities.get("specialization"):
            flow_data["specialization"] = entities["specialization"]
        if entities.get("date"):
            flow_data["date"] = entities["date"]
        if entities.get("slot"):
            flow_data["slot"] = entities["slot"]
        if entities.get("reason"):
            flow_data["reason"] = entities["reason"]

        # 1. Resolve Doctor
        doc_query = entities.get("doctor_name")
        presented_docs = flow_data.get("presented_doctors", [])
        if not flow_data.get("doctor_id") and presented_docs:
            ref_doc = resolve_doctor_reference(query, presented_docs)
            if ref_doc:
                flow_data["doctor_id"] = ref_doc["id"]
                flow_data["doctor_name"] = ref_doc.get("name") or f"Dr. {ref_doc.get('first_name')} {ref_doc.get('last_name')}"
                flow_data["hospital_id"] = ref_doc.get("hospital_id")
                flow_data["hospital_name"] = ref_doc.get("hospital_name") or "Central Branch"
                flow_data["specialization"] = ref_doc.get("specialization") or flow_data.get("specialization")

        if doc_query and not flow_data.get("doctor_id"):
            active_docs = await list_active_doctors()
            matched = [
                d for d in active_docs
                if doc_query.lower() in f"{d.get('first_name', '')} {d.get('last_name', '')}".lower()
            ]
            if matched:
                doc = matched[0]
                flow_data["doctor_id"] = doc["id"]
                flow_data["doctor_name"] = f"Dr. {doc.get('first_name')} {doc.get('last_name')}"
                flow_data["hospital_id"] = doc.get("hospital_id")
                flow_data["hospital_name"] = doc.get("hospital_name") or "Central Branch"
                flow_data["specialization"] = doc.get("specialization") or flow_data.get("specialization")

        # Doctor ID present?
        doc_id = flow_data.get("doctor_id")
        if not doc_id:
            # Need to select doctor
            spec = flow_data.get("specialization")
            doctors = await list_active_doctors(specialization=spec)
            if not doctors:
                doctors = await list_active_doctors()

            flow_data["presented_doctors"] = [
                {
                    "id": d["id"],
                    "name": f"Dr. {d.get('first_name')} {d.get('last_name')}",
                    "first_name": d.get("first_name"),
                    "last_name": d.get("last_name"),
                    "specialization": d.get("specialization"),
                    "hospital_id": d.get("hospital_id"),
                    "hospital_name": d.get("hospital_name") or "Central Branch",
                }
                for d in doctors[:6]
            ]

            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="select_doctor",
                flow_data=flow_data,
            )

            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text="Which doctor would you like to see?",
                session=session,
                reply_markup=doctors_keyboard(doctors[:6]),
            )
            return

        # 2. Resolve Date
        target_date = flow_data.get("date")
        if not target_date:
            today = get_current_date_in_tz()
            dates = [
                {"date": today.isoformat(), "label": f"Today ({today.strftime('%a')})"},
                {"date": (today + timedelta(days=1)).isoformat(), "label": f"Tomorrow ({(today + timedelta(days=1)).strftime('%a')})"},
                {"date": (today + timedelta(days=2)).isoformat(), "label": (today + timedelta(days=2)).strftime('%a, %b %d')},
            ]

            d_name = escape_markdown(flow_data.get("doctor_name", "the doctor"))
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="select_date",
                flow_data=flow_data,
            )

            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text=f"*{d_name}* is available for appointments\\. Which day would you prefer?",
                session=session,
                reply_markup=dates_keyboard(dates),
            )
            return

        # 3. Resolve Slot
        avail = await get_doctor_availability(doc_id, target_date)
        if not avail.get("is_available") or not avail.get("available_slots"):
            date_esc = escape_markdown(target_date)
            d_name = escape_markdown(flow_data.get("doctor_name", "Doctor"))
            # Clear date so user can pick another
            flow_data.pop("date", None)
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="select_date",
                flow_data=flow_data,
            )
            await self.adapter.send_message(
                chat_id=chat_id,
                text=f"Unfortunately *{d_name}* has no open slots on *{date_esc}*\\. Could you choose a different date?",
            )
            return

        open_slots = avail.get("available_slots", [])
        flow_data["presented_slots"] = open_slots[:12]
        slot = flow_data.get("slot")

        if not slot:
            ref_slot = resolve_slot_reference(query, open_slots[:12])
            if ref_slot:
                slot = ref_slot
                flow_data["slot"] = slot

        if not slot or slot not in open_slots:
            # If user typed slot that doesn't match perfectly, check normalized
            matched_slot = None
            if slot:
                for s in open_slots:
                    if slot.lower().replace(" ", "") == s.lower().replace(" ", ""):
                        matched_slot = s
                        break

            if matched_slot:
                slot = matched_slot
                flow_data["slot"] = slot
            else:
                flow_data.pop("slot", None)
                await SessionManager.update_flow(
                    session_key=session.session_key,
                    current_flow=TelegramFlowType.BOOKING.value,
                    flow_step="select_slot",
                    flow_data=flow_data,
                )
                d_name = escape_markdown(flow_data.get("doctor_name", "Doctor"))
                date_esc = escape_markdown(target_date)
                slots_preview = ", ".join(open_slots[:2])
                await send_conversational_response(
                    adapter=self.adapter,
                    chat_id=chat_id,
                    text=f"Here are the available slots for *{d_name}* on *{date_esc}*\\. Which time works best for you?",
                    session=session,
                    reply_markup=slots_keyboard(open_slots[:12]),
                )
                return

        # 4. Resolve Reason / Symptoms
        reason = flow_data.get("reason")
        if not reason:
            is_slot_ref = bool(re.search(r"^\b(10|11|12|[1-9]):[0-5][0-9]\b", query) or re.search(r"\b(first|second|third|slot)\b", query.lower()))
            if len(query.split()) > 2 and not is_slot_ref:
                reason = query
                flow_data["reason"] = reason
            else:
                await SessionManager.update_flow(
                    session_key=session.session_key,
                    current_flow=TelegramFlowType.BOOKING.value,
                    flow_step="enter_reason",
                    flow_data=flow_data,
                )
                d_name = escape_markdown(flow_data.get("doctor_name", "Doctor"))
                slot_esc = escape_markdown(slot)
                await self.adapter.send_message(
                    chat_id=chat_id,
                    text=f"Great\\! {slot_esc} with *{d_name}*\\. What symptoms or consultation reason should we note for the doctor?",
                )
                return

        # 5. Check Patient Authentication Before Final Confirmation
        if not patient:
            # Save pending booking into flow_data and transition to conversational registration
            flow_data["pending_booking"] = {
                "doctor_id": doc_id,
                "doctor_name": flow_data.get("doctor_name"),
                "hospital_id": flow_data.get("hospital_id"),
                "hospital_name": flow_data.get("hospital_name"),
                "specialization": flow_data.get("specialization"),
                "date": target_date,
                "slot": slot,
                "reason": reason,
            }

            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.REGISTRATION.value,
                flow_step="enter_name",
                flow_data=flow_data,
            )

            await self.adapter.send_message(
                chat_id=chat_id,
                text=(
                    "It looks like you don't have a patient profile with CityCare yet\\. "
                    "I can help you register right now so we can secure your appointment with "
                    f"*{escape_markdown(flow_data.get('doctor_name', 'your doctor'))}*\\.\n\n"
                    "What's your full name?"
                ),
            )
            return

        # 6. Show Booking Confirmation Summary Card
        if session.flow_step != "confirm_booking" and entities.get("intent") != "confirm_action":
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="confirm_booking",
                flow_data=flow_data,
            )

            h_name = escape_markdown(flow_data.get("hospital_name", "CityCare Central"))
            d_name = escape_markdown(flow_data.get("doctor_name", "Specialist Doctor"))
            dept = escape_markdown(flow_data.get("specialization", "General Medicine"))
            date_val = escape_markdown(target_date)
            slot_val = escape_markdown(slot)
            reason_esc = escape_markdown(reason)

            summary = f"""📋 *Appointment Summary* — Here's what I have:

👨‍⚕️ *Doctor:* {d_name}
🩺 *Department:* {dept}
🏥 *Hospital:* {h_name}
📅 *Date:* {date_val}
⏰ *Time:* {slot_val}
📝 *Reason:* {reason_esc}

Would you like me to book this appointment?"""

            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text=summary,
                session=session,
                reply_markup=confirmation_keyboard(),
            )
            return

        # 7. Execute Booking Atomically via Medihub Service
        try:
            res = await book_patient_appointment(
                patient=patient,
                date_str=target_date,
                slot=slot,
                reason=reason,
                hospital_id=flow_data.get("hospital_id"),
                doctor_id=doc_id,
            )
            await SessionManager.clear_flow(session.session_key)

            appt_id = escape_markdown(res.get("id", ""))
            d_name = escape_markdown(flow_data.get("doctor_name", "Specialist Doctor"))
            h_name = escape_markdown(flow_data.get("hospital_name", "Central Clinic"))

            confirm_text = f"""✅ *Appointment Confirmed\\!*

You're booked with *{d_name}* at *{h_name}* on *{escape_markdown(target_date)}* at *{escape_markdown(slot)}*\\. Your appointment has been confirmed\\.

🆔 *Booking Reference:* `{appt_id}`
📝 *Reason:* {escape_markdown(reason)}

_Please arrive 15 minutes before your scheduled appointment time\\._"""

            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text=confirm_text,
                session=session,
                reply_markup=compact_menu_keyboard(is_verified=True),
            )
        except SlotConflictError:
            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text="⚠️ *Slot Conflict*\n\nThat slot was just booked by another patient\\. Please choose another available slot:",
                session=session,
                reply_markup=slots_keyboard(open_slots),
            )
        except BookingError as exc:
            await self.adapter.send_message(
                chat_id=chat_id,
                text=f"❌ *Booking Error:* {escape_markdown(str(exc))}",
            )

    async def _handle_context_switch(
        self,
        chat_id: int,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
        query: str,
        entities: Dict[str, Any],
    ) -> None:
        """Handle patient changing mind: 'Actually, I want a different doctor' or 'Actually Friday'."""
        flow_data = dict(session.flow_data or {})
        lower = query.lower()

        # 1. Date change
        if (
            entities.get("switch") == "date"
            or re.search(r"\b(change\s*(?:the\s*)?date|different\s*date|another\s*date|actually\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today))\b", lower)
            or (flow_data.get("doctor_id") and entities.get("date") and not entities.get("doctor_name"))
        ):
            flow_data.pop("slot", None)
            flow_data.pop("presented_slots", None)
            new_date = entities.get("date") or parse_relative_date(query)
            if new_date:
                flow_data["date"] = new_date
                doc_id = flow_data.get("doctor_id")
                d_name = escape_markdown(flow_data.get("doctor_name", "the doctor"))
                avail = await get_doctor_availability(doc_id, new_date)
                if avail.get("is_available") and avail.get("available_slots"):
                    open_slots = avail.get("available_slots", [])
                    flow_data["presented_slots"] = open_slots[:12]
                    await SessionManager.update_flow(
                        session_key=session.session_key,
                        current_flow=TelegramFlowType.BOOKING.value,
                        flow_step="select_slot",
                        flow_data=flow_data,
                    )
                    date_esc = escape_markdown(new_date)
                    await send_conversational_response(
                        adapter=self.adapter,
                        chat_id=chat_id,
                        text=f"No problem\\! I've updated the date to *{date_esc}* for *{d_name}*\\. Which time slot works best for you?",
                        session=session,
                        reply_markup=slots_keyboard(open_slots[:12]),
                    )
                    return
                else:
                    flow_data.pop("date", None)
                    await SessionManager.update_flow(
                        session_key=session.session_key,
                        current_flow=TelegramFlowType.BOOKING.value,
                        flow_step="select_date",
                        flow_data=flow_data,
                    )
                    date_esc = escape_markdown(new_date)
                    await self.adapter.send_message(
                        chat_id=chat_id,
                        text=f"*{d_name}* has no open slots on *{date_esc}*\\. What date would work best for you?",
                    )
                    return
            else:
                flow_data.pop("date", None)
                await SessionManager.update_flow(
                    session_key=session.session_key,
                    current_flow=TelegramFlowType.BOOKING.value,
                    flow_step="select_date",
                    flow_data=flow_data,
                )
                await self.adapter.send_message(
                    chat_id=chat_id,
                    text="What date would work best for you?",
                )
                return

        # 2. Doctor change
        spec = flow_data.get("specialization")
        old_doc_id = flow_data.get("doctor_id")

        flow_data.pop("doctor_id", None)
        flow_data.pop("doctor_name", None)
        flow_data.pop("slot", None)
        flow_data.pop("presented_slots", None)

        doctors = await list_active_doctors(specialization=spec)
        if not doctors:
            doctors = await list_active_doctors()

        other_doctors = [d for d in doctors if d["id"] != old_doc_id]
        if other_doctors:
            doctors = other_doctors

        flow_data["presented_doctors"] = [
            {
                "id": d["id"],
                "name": f"Dr. {d.get('first_name')} {d.get('last_name')}",
                "first_name": d.get("first_name"),
                "last_name": d.get("last_name"),
                "specialization": d.get("specialization"),
                "hospital_id": d.get("hospital_id"),
                "hospital_name": d.get("hospital_name") or "Central Branch",
            }
            for d in doctors[:6]
        ]

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="select_doctor",
            flow_data=flow_data,
        )

        spec_text = f" in *{escape_markdown(spec)}*" if spec else ""
        await send_conversational_response(
            adapter=self.adapter,
            chat_id=chat_id,
            text=f"No problem\\! I'll look for another doctor with the same specialty{spec_text}\\. Which doctor would you prefer?",
            session=session,
            reply_markup=doctors_keyboard(doctors[:6]),
        )

    async def _handle_registration_flow(
        self,
        chat_id: int,
        user_id: int,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
        query: str,
        entities: Dict[str, Any],
        from_user: Dict[str, Any],
    ) -> None:
        """Conversational registration supporting multi-entity extraction and confirmation card."""
        if patient:
            p_name = escape_markdown(f"{patient.get('first_name')} {patient.get('last_name')}")
            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text=f"ℹ️ *Already Registered*\n\nYou already have an active profile linked as *{p_name}*\\.",
                session=session,
                reply_markup=compact_menu_keyboard(is_verified=True),
            )
            return

        flow_data = dict(session.flow_data or {})
        extracted = extract_registration_entities(query)

        # Merge extracted entities
        for k, v in extracted.items():
            if v and not flow_data.get(k):
                flow_data[k] = v

        # Check confirmation intent when in confirmation step
        is_confirm = bool(
            re.search(r"^\b(yes|confirm|proceed|create|create profile|looks good|correct|agree|sure|book it|book|go ahead)\b", query.lower())
        )
        is_cancel = bool(re.search(r"^\b(cancel|no|stop|forget it)\b", query.lower()))
        is_edit = bool(re.search(r"^\b(edit|change|update)\b", query.lower()))

        if is_cancel:
            await SessionManager.clear_flow(session.session_key)
            await self.adapter.send_message(
                chat_id=chat_id,
                text="❌ *Registration Cancelled*\n\nYour temporary registration details have been cleared\\. How else can I help you?",
            )
            return

        if session.flow_step == "confirm_registration" and is_confirm:
            await self._finalize_registration(chat_id, user_id, session, flow_data)
            return

        if session.flow_step == "confirm_registration" and is_edit:
            await self.adapter.send_message(
                chat_id=chat_id,
                text="Which detail would you like to update? You can send your updated Name, Date of Birth, Email, or Mobile number\\.",
            )
            return

        # Determine what's missing
        has_name = bool(flow_data.get("first_name") and flow_data.get("last_name"))
        has_dob = bool(flow_data.get("dob"))
        has_email = bool(flow_data.get("email"))
        has_mobile = bool(flow_data.get("mobile"))

        # Step 1: Missing Name
        if not has_name:
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.REGISTRATION.value,
                flow_step="enter_name",
                flow_data=flow_data,
            )
            await self.adapter.send_message(
                chat_id=chat_id,
                text="📝 *New Patient Registration*\n\nWhat is your full name? \\(e\\.g\\. `Rudra Dalal`\\)",
            )
            return

        # Step 2: Missing DOB
        if not has_dob:
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.REGISTRATION.value,
                flow_step="enter_dob",
                flow_data=flow_data,
            )
            first_name = escape_markdown(flow_data.get("first_name", ""))
            await self.adapter.send_message(
                chat_id=chat_id,
                text=f"Thanks, *{first_name}*\\! What is your date of birth? \\(e\\.g\\. `12 May 2004` or `DD/MM/YYYY`\\)",
            )
            return

        # Step 3: Missing Email
        if not has_email:
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.REGISTRATION.value,
                flow_step="enter_email",
                flow_data=flow_data,
            )
            first_name = escape_markdown(flow_data.get("first_name", ""))
            await self.adapter.send_message(
                chat_id=chat_id,
                text=f"Thanks, *{first_name}*\\! And what email address should we use for your patient profile and prescriptions?",
            )
            return

        # Step 4: Missing Mobile
        if not has_mobile:
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.REGISTRATION.value,
                flow_step="enter_mobile",
                flow_data=flow_data,
            )
            await self.adapter.send_message(
                chat_id=chat_id,
                text="📱 What 10\\-digit mobile number should we use for your patient profile? \\(e\\.g\\. `9876543210` or `+919876543210`\\)",
            )
            return

        # All fields present -> Show concise confirmation summary card
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="confirm_registration",
            flow_data=flow_data,
        )

        name_esc = escape_markdown(f"{flow_data.get('first_name')} {flow_data.get('last_name')}")
        dob_esc = escape_markdown(flow_data.get("dob", "Not specified"))
        email_esc = escape_markdown(flow_data.get("email"))
        mob_esc = escape_markdown(flow_data.get("mobile"))

        summary = f"""Here's what I have:

• *Name:* {name_esc}
• *Date of Birth:* {dob_esc}
• *Email:* {email_esc}
• *Mobile:* {mob_esc}

Would you like me to create your patient profile?"""

        await send_conversational_response(
            adapter=self.adapter,
            chat_id=chat_id,
            text=summary,
            session=session,
            reply_markup=registration_summary_keyboard(),
        )

    async def _finalize_registration(
        self,
        chat_id: int,
        user_id: int,
        session: TelegramSession,
        flow_data: Dict[str, Any],
    ) -> None:
        """Create patient in Medihub backend, link Telegram ID, and resume pending bookings."""
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
                    "password": "",  # Generates one-time activation token
                },
                consent=consent_obj,
                allow_activation_token=True,
            )
        except Exception as exc:
            logger.error("Registration failed in assistant: %s", exc)
            err_msg = escape_markdown(str(exc))
            await self.adapter.send_message(
                chat_id=chat_id,
                text=f"❌ *Registration Error:* {err_msg}\n\nPlease try /register again.",
                reply_markup=main_menu_keyboard(is_verified=False),
            )
            await SessionManager.clear_flow(session.session_key)
            return

        patient_id = patient_record["id"]

        # Link Telegram Identity
        await IdentityManager.link_patient(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            patient_id=patient_id,
            consent=consent_obj,
        )

        await SessionManager.set_patient_id(session.session_key, patient_id)

        p_name = escape_markdown(f"{patient_record.get('first_name')} {patient_record.get('last_name')}")
        act_url = patient_record.get("activation_url", "")
        act_url_esc = escape_markdown(act_url) if act_url else ""

        welcome = f"""🎉 *Registration Successful\\!*

Welcome to CityCare, *{p_name}*\\! Your Telegram account is now securely linked\\.

🔑 *Web Portal Password Setup:*
You can set your web login password at:
[Set Web Password]({act_url_esc})

_All Telegram assistant features are now fully unlocked\\._"""

        # Check for pending booking
        pending = flow_data.get("pending_booking")
        if pending:
            await self.adapter.send_message(chat_id=chat_id, text=welcome)

            # Re-fetch patient user doc
            _, full_patient = await IdentityManager.resolve_identity(user_id)
            # Update session flow to booking confirmation
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="confirm_booking",
                flow_data=pending,
            )

            d_name = escape_markdown(pending.get("doctor_name", "Doctor"))
            h_name = escape_markdown(pending.get("hospital_name", "Hospital"))
            date_val = escape_markdown(pending.get("date", ""))
            slot_val = escape_markdown(pending.get("slot", ""))
            reason_esc = escape_markdown(pending.get("reason", "General Consultation"))

            resume_text = f"""Now, let's complete your appointment booking:

🏥 *Hospital:* {h_name}
👨‍⚕️ *Doctor:* {d_name}
📅 *Date:* {date_val}
⏰ *Time:* {slot_val}
📝 *Reason:* {reason_esc}

Would you like to confirm this booking?"""

            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text=resume_text,
                session=session,
                reply_markup=confirmation_keyboard(),
            )
        else:
            await SessionManager.clear_flow(session.session_key)
            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text=welcome,
                session=session,
                reply_markup=compact_menu_keyboard(is_verified=True),
            )

    async def _handle_view_appointments(
        self,
        chat_id: int,
        patient: Optional[Dict[str, Any]],
        session: Optional[TelegramSession] = None,
    ) -> None:
        """Display appointments for verified patient with cancellation option."""
        if not patient:
            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text="🔒 To view your appointment history, please link your CityCare account with /link or register with /register.",
                session=session,
                reply_markup=compact_menu_keyboard(is_verified=False),
            )
            return

        patient_id = str(patient["_id"])
        appts = await get_patient_appointments(patient_id)
        if not appts:
            await send_conversational_response(
                adapter=self.adapter,
                chat_id=chat_id,
                text="📋 *My Appointments*\n\nYou do not have any scheduled appointments\\.\n\nYou can say *'Book an appointment'* anytime to see a doctor\\.",
                session=session,
                reply_markup=compact_menu_keyboard(is_verified=True),
            )
            return

        lines = ["📋 *Your CityCare Appointments:*\n"]
        buttons = []
        for a in appts[:6]:
            a_id = a.get("id")
            d_name = escape_markdown(a.get("doctor_name", "Specialist Doctor"))
            h_name = escape_markdown(a.get("hospital_name", "Central Branch"))
            d_val = escape_markdown(a.get("date", ""))
            s_val = escape_markdown(a.get("slot", ""))
            st_val = escape_markdown(a.get("status", "Booked").capitalize())
            reason_esc = escape_markdown(a.get("reason", "Consultation"))

            lines.append(f"• *{d_val} at {s_val}* \\({st_val}\\)\n  👨‍⚕️ {d_name} | 🏥 {h_name}\n  📝 Reason: {reason_esc}")

            if a.get("status") in ("booked", "accepted"):
                buttons.append([{"text": f"❌ Cancel {d_val} ({s_val})", "callback_data": f"appt:cancel:{a_id}"}])

        buttons.append([{"text": "📅 Book New Appointment", "callback_data": "nav:book"}])
        buttons.append([{"text": "🔙 Main Menu", "callback_data": "nav:main"}])

        await send_conversational_response(
            adapter=self.adapter,
            chat_id=chat_id,
            text="\n".join(lines),
            session=session,
            reply_markup=build_inline_keyboard(buttons),
        )

    async def _handle_cancel_appointment(
        self,
        chat_id: int,
        patient: Optional[Dict[str, Any]],
        entities: Dict[str, Any],
        query: str,
    ) -> None:
        """Cancel patient appointment conversationally."""
        if not patient:
            await self.adapter.send_message(
                chat_id=chat_id,
                text="🔒 To manage your appointments, please link your account with /link or register with /register.",
                reply_markup=main_menu_keyboard(is_verified=False),
            )
            return

        patient_id = str(patient["_id"])
        appts = await get_patient_appointments(patient_id)
        active_appts = [a for a in appts if a.get("status") in ("booked", "accepted")]

        if not active_appts:
            await self.adapter.send_message(
                chat_id=chat_id,
                text="ℹ️ You do not have any active appointments to cancel\\.",
                reply_markup=main_menu_keyboard(is_verified=True),
            )
            return

        # If only 1 appointment, cancel it directly
        if len(active_appts) == 1:
            target = active_appts[0]
            try:
                await cancel_patient_appointment(appointment_id=target["id"], patient_id=patient_id)
                d_val = escape_markdown(target.get("date"))
                s_val = escape_markdown(target.get("slot"))
                d_name = escape_markdown(target.get("doctor_name", "your doctor"))
                await self.adapter.send_message(
                    chat_id=chat_id,
                    text=f"✅ Your appointment with *{d_name}* on *{d_val} at {s_val}* has been successfully cancelled\\.",
                    reply_markup=main_menu_keyboard(is_verified=True),
                )
            except Exception as exc:
                await self.adapter.send_message(
                    chat_id=chat_id,
                    text=f"❌ Failed to cancel appointment: {escape_markdown(str(exc))}",
                    reply_markup=main_menu_keyboard(is_verified=True),
                )
            return

        # If multiple, present choices
        buttons = []
        for a in active_appts:
            d_val = a.get("date")
            s_val = a.get("slot")
            buttons.append([{"text": f"❌ Cancel {d_val} ({s_val})", "callback_data": f"appt:cancel:{a['id']}"}])
        buttons.append([{"text": "🔙 Keep Appointments", "callback_data": "nav:main"}])

        await self.adapter.send_message(
            chat_id=chat_id,
            text="Which appointment would you like to cancel?",
            reply_markup=build_inline_keyboard(buttons),
        )

    async def _handle_hospital_info(self, chat_id: int, entities: Dict[str, Any]) -> None:
        """Display hospital branches and facilities."""
        hospitals = await list_active_hospitals()
        if not hospitals:
            await self.adapter.send_message(
                chat_id=chat_id,
                text="🏥 *CityCare Hospital Branches*\n\nNo active branches found\\.",
                reply_markup=main_menu_keyboard(),
            )
            return

        lines = ["🏥 *CityCare Hospital Branches & Facilities:*\n"]
        for h in hospitals:
            name = escape_markdown(h.get("name"))
            city = escape_markdown(h.get("city"))
            phone = escape_markdown(h.get("contact_phone"))
            hours = escape_markdown(h.get("working_hours"))
            facs = ", ".join(escape_markdown(f) for f in h.get("facilities", [])[:3])
            lines.append(f"• *{name}* \\({city}\\)\n  📞 {phone} | 🕒 {hours}\n  🏢 Facilities: {facs}...")

        lines.append("\nYou can book an appointment or view doctor schedules anytime\\.")
        await self.adapter.send_message(
            chat_id=chat_id,
            text="\n".join(lines),
            reply_markup=hospitals_keyboard(hospitals, callback_prefix="view:hosp:"),
        )

    async def _handle_help(
        self,
        chat_id: int,
        patient: Optional[Dict[str, Any]],
        session: Optional[TelegramSession] = None,
    ) -> None:
        """Help and usage guidance."""
        help_msg = """🏥 *CityCare Patient Assistant Guide*

I can assist you naturally with your healthcare needs\\! Just type what you want, for example:

📅 *Appointments & Doctors:*
• _"I need a dermatologist tomorrow"_
• _"Show available cardiologists"_
• _"I want Dr Sharma"_
• _"Book me for tomorrow at 10:30"_
• _"Show my appointments"_

💊 *Prescriptions:*
• _"Show my latest prescription"_
• _"What medicines did my doctor prescribe?"_

👤 *Account:*
• _"I need to register"_
• _"My name is Rudra Dalal and my DOB is 12/05/2004"_

🔄 *Controls:*
• _"Actually, I want a different doctor"_
• _"I changed my mind" / /cancel_"""

        await send_conversational_response(
            adapter=self.adapter,
            chat_id=chat_id,
            text=help_msg,
            session=session,
            reply_markup=compact_menu_keyboard(is_verified=bool(patient)),
        )

    async def _handle_general_fallback(
        self,
        chat_id: int,
        session: TelegramSession,
        patient: Optional[Dict[str, Any]],
        query: str,
        entities: Dict[str, Any],
    ) -> None:
        """Conversational fallback for open-ended questions."""
        from telegram_gateway.flows.chat_flow import handle_ai_health_chat
        await handle_ai_health_chat(
            adapter=self.adapter,
            chat_id=chat_id,
            text=query,
            patient=patient,
        )
