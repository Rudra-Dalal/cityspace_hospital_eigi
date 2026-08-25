"""
CityCare Doctor AI Service — Gemini integration with tool-based architecture.

Architecture:
  AIChatRequest  →  run_chat()
                       ↓
                   Gemini (function calling via google-genai SDK)
                       ↓
                   Tool Registry (read-only, auth-injected)
                       ↓
                   Existing CRUD / MongoDB
                       ↓
                   Gemini (final response)
                       ↓
                   AIChatResponse

Conversation state is held in-memory (dict keyed by UUID).
Uses the current google-genai SDK (not the deprecated google-generativeai).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.ai.prompt import SYSTEM_PROMPT
from app.ai.tools import TOOL_REGISTRY, execute_tool
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas for Gemini function-calling
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS = [
    {
        "name": "get_today_schedule",
        "description": "Get the authenticated doctor's appointments for today.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_schedule_for_date",
        "description": "Get the doctor's appointments for a specific date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD, e.g. 2026-08-10",
                }
            },
            "required": ["date"],
        },
    },
    {
        "name": "get_appointment_details",
        "description": "Get full details of a specific appointment by its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "The appointment ID (MongoDB ObjectId string).",
                }
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "search_my_patients",
        "description": "Search for patients by name among those who have appointments with this doctor.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Patient name search string (minimum 2 characters).",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_patient_summary",
        "description": "Get a summary of a patient's information and appointment count.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "The patient's user ID.",
                }
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_patient_history",
        "description": "Get the appointment history for a patient with this doctor.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "The patient's user ID.",
                }
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_today_statistics",
        "description": "Get appointment statistics for today (total, booked, cancelled).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

# ---------------------------------------------------------------------------
# In-memory conversation store
# { conversation_id: [{"role": "user"|"model", "parts": [...]}] }
# ---------------------------------------------------------------------------

_conversations: Dict[str, List[Dict[str, Any]]] = {}
_conversation_last_access: Dict[str, float] = {}

MAX_TURNS = 20               # max user+model turn pairs to retain
CONVERSATION_TTL = 3 * 3600  # 3 hours in seconds

# ---------------------------------------------------------------------------
# Rate limiter (per user)
# ---------------------------------------------------------------------------

_rate_windows: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_PER_MINUTE = 20


def _check_rate_limit(user_id: str) -> bool:
    now = time.monotonic()
    window = _rate_windows[user_id]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return False
    window.append(now)
    return True


def _cleanup_conversations() -> None:
    now = time.monotonic()
    stale = [cid for cid, ts in _conversation_last_access.items() if now - ts > CONVERSATION_TTL]
    for cid in stale:
        _conversations.pop(cid, None)
        _conversation_last_access.pop(cid, None)


def _get_or_create_conversation(conversation_id: Optional[str]) -> Tuple[str, List[Dict[str, Any]]]:
    _cleanup_conversations()
    if conversation_id and conversation_id in _conversations:
        _conversation_last_access[conversation_id] = time.monotonic()
        return conversation_id, _conversations[conversation_id]
    new_id = uuid.uuid4().hex
    _conversations[new_id] = []
    _conversation_last_access[new_id] = time.monotonic()
    return new_id, _conversations[new_id]


def _trim_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the most recent MAX_TURNS turn-pairs."""
    max_entries = MAX_TURNS * 2
    return history[-max_entries:] if len(history) > max_entries else history


async def _fallback_doctor_reply(message: str, current_user: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    High-reliability local clinical resolution when Gemini external API is rate-limited or unavailable.
    Directly executes real database tools to provide accurate appointments, schedules, and metrics.
    """
    msg = message.lower().strip()
    tools_called: List[str] = []
    
    # 1. Check for tomorrow's schedule
    if "tomorrow" in msg:
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        tools_called.append("get_schedule_for_date")
        data = await execute_tool("get_schedule_for_date", {"date": tomorrow}, current_user)
        appts = data.get("appointments", [])
        if not appts:
            return (
                f"### Consulting Schedule for Tomorrow ({tomorrow})\n\n"
                f"You have **no scheduled appointments** for tomorrow. All consultation slots are currently open.",
                tools_called,
            )
        lines = [
            f"### Consulting Schedule for Tomorrow ({tomorrow})",
            f"You have **{len(appts)}** scheduled consultation(s):\n",
        ]
        for a in appts:
            p_name = a.get("patient_name", "Patient")
            slot = a.get("slot", "TBD")
            status = a.get("status", "booked").capitalize()
            reason = a.get("reason", "General Consultation")
            symptoms = ", ".join(a.get("symptoms", []))
            sym_text = f" (Reported Symptoms: {symptoms})" if symptoms else ""
            lines.append(f"- **{slot}** — **{p_name}** [{status}] • *{reason}*{sym_text}")
        return "\n".join(lines), tools_called

    # 2. Check for stats/metrics/attendance
    if any(k in msg for k in ["stat", "metric", "attendance", "overview", "count", "performance"]):
        tools_called.append("get_today_statistics")
        data = await execute_tool("get_today_statistics", {}, current_user)
        total = data.get("total", 0)
        booked = data.get("booked", 0)
        completed = data.get("completed", 0)
        cancelled = data.get("cancelled", 0)
        return (
            f"### Today's Clinic Attendance & Consultation Metrics\n\n"
            f"- **Total Consultations Today:** {total}\n"
            f"- **Active Booked:** {booked}\n"
            f"- **Completed Consultations:** {completed}\n"
            f"- **Cancelled Slots:** {cancelled}",
            tools_called,
        )

    # 3. Check for specific date (YYYY-MM-DD)
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", msg)
    if date_match:
        target_date = date_match.group(0)
        tools_called.append("get_schedule_for_date")
        data = await execute_tool("get_schedule_for_date", {"date": target_date}, current_user)
        appts = data.get("appointments", [])
        if not appts:
            return (
                f"### Consulting Schedule for {target_date}\n\n"
                f"You have **no appointments scheduled** for {target_date}.",
                tools_called,
            )
        lines = [f"### Consulting Schedule for {target_date}", f"You have **{len(appts)}** scheduled consultation(s):\n"]
        for a in appts:
            p_name = a.get("patient_name", "Patient")
            slot = a.get("slot", "TBD")
            status = a.get("status", "booked").capitalize()
            reason = a.get("reason", "Consultation")
            lines.append(f"- **{slot}** — **{p_name}** [{status}] • *{reason}*")
        return "\n".join(lines), tools_called

    # 4. Check for today's schedule / upcoming bookings / patient queue
    if any(k in msg for k in ["today", "schedule", "upcoming", "booking", "patient", "queue", "roster"]):
        tools_called.append("get_today_schedule")
        data = await execute_tool("get_today_schedule", {}, current_user)
        today = data.get("date", "today")
        appts = data.get("appointments", [])
        if not appts:
            return (
                f"### Today's Consultation Schedule ({today})\n\n"
                f"Your queue is currently **clear** with no appointments scheduled for today.",
                tools_called,
            )
        lines = [f"### Today's Consultation Schedule ({today})", f"You have **{len(appts)}** appointment(s) scheduled:\n"]
        for a in appts:
            p_name = a.get("patient_name", "Patient")
            slot = a.get("slot", "TBD")
            status = a.get("status", "booked").capitalize()
            reason = a.get("reason", "Consultation")
            lines.append(f"- **{slot}** — **{p_name}** [{status}] • *{reason}*")
        return "\n".join(lines), tools_called

    # Default friendly guidance
    return (
        "I am your Clinical AI Assistant. You can ask me about:\n\n"
        "- **Your Schedule:** *'What appointments do I have today?'* or *'What is my consulting schedule tomorrow?'*\n"
        "- **Clinic Metrics:** *'Give me today's clinic attendance metrics.'*\n"
        "- **Upcoming Bookings:** *'Show me my upcoming patient bookings.'*",
        [],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_chat(
    message: str,
    conversation_id: Optional[str],
    current_user: Dict[str, Any],
) -> Tuple[str, str, List[str]]:
    """
    Process a chat message and return (reply, conversation_id, tool_calls_made).
    Tries Google Gemini function-calling first, with instant deterministic fallback
    if Gemini is rate-limited, offline, or times out.
    """
    user_id = str(current_user["_id"])

    if not _check_rate_limit(user_id):
        logger.warning("AI_RATE_LIMITED user=%s", current_user.get("email"))
        raise ValueError("rate_limited")

    conv_id, history = _get_or_create_conversation(conversation_id)
    logger.info("AI_REQUEST user=%s conv=%s", current_user.get("email"), conv_id)

    settings = get_settings()
    api_key: str = getattr(settings, "gemini_api_key", "") or ""
    model_name: str = getattr(settings, "gemini_model", "gemini-3.6-flash")
    temperature: float = float(getattr(settings, "gemini_temperature", 0.2))
    max_output_tokens: int = int(getattr(settings, "gemini_max_output_tokens", 2048))

    # If no API key is provided, use instant local database tools
    if not api_key or api_key.startswith("your-"):
        logger.info("AI using direct database tools (no API key configured)")
        reply_text, tools_called = await _fallback_doctor_reply(message, current_user)
        return reply_text, conv_id, tools_called

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        logger.warning("google-genai not installed, using direct database tools")
        reply_text, tools_called = await _fallback_doctor_reply(message, current_user)
        return reply_text, conv_id, tools_called

    try:
        client = genai.Client(api_key=api_key)

        # Build tool config
        tools = [
            genai_types.Tool(
                function_declarations=[
                    genai_types.FunctionDeclaration(
                        name=t["name"],
                        description=t["description"],
                        parameters=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                k: genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description=v.get("description", ""),
                                )
                                for k, v in t["parameters"].get("properties", {}).items()
                            },
                            required=t["parameters"].get("required", []),
                        ),
                    )
                    for t in _TOOL_SCHEMAS
                ]
            )
        ]

        generate_config = genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            tools=tools,
        )

        # Rebuild full conversation contents for the API call
        trimmed = _trim_history(list(history))
        contents: List[Any] = []
        for entry in trimmed:
            contents.append(genai_types.Content(role=entry["role"], parts=entry["parts"]))

        # Add the new user message
        contents.append(genai_types.Content(role="user", parts=[genai_types.Part(text=message)]))

        tools_called: List[str] = []
        response = None

        # Agentic loop — Gemini may request multiple tool calls
        for _iteration in range(10):
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=generate_config,
                ),
                timeout=12.0,
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate:
                break

            # Collect function calls from this response
            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if hasattr(part, "function_call") and part.function_call and part.function_call.name
            ]

            if not function_calls:
                # No tool calls — final text response
                contents.append(candidate.content)
                break

            # Append model's tool-call message to contents
            contents.append(candidate.content)

            # Execute each tool and collect responses
            tool_response_parts = []
            for fc in function_calls:
                tool_name = fc.name
                raw_args = dict(fc.args) if fc.args else {}

                if tool_name not in TOOL_REGISTRY:
                    logger.warning("AI_UNKNOWN_TOOL tool=%s user=%s", tool_name, current_user.get("email"))
                    result = {"error": f"Unknown tool: {tool_name!r}"}
                else:
                    tools_called.append(tool_name)
                    result = await execute_tool(tool_name, raw_args, current_user)

                logger.info(
                    "AI_TOOL_RESULT tool=%s keys=%s user=%s",
                    tool_name,
                    list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                    current_user.get("email"),
                )

                tool_response_parts.append(
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=tool_name,
                            response={"result": result},
                        )
                    )
                )

            # Add tool results as a user turn
            contents.append(genai_types.Content(role="user", parts=tool_response_parts))

        # Extract text reply
        reply_text = ""
        if response:
            try:
                reply_text = response.text
            except Exception:
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "text") and part.text:
                            reply_text += part.text

        if not reply_text:
            reply_text = "I was unable to generate a response. Please try again."

        # Persist updated history
        history.clear()
        for c in contents:
            if hasattr(c, "role") and hasattr(c, "parts"):
                history.append({"role": c.role, "parts": c.parts})
        _conversation_last_access[conv_id] = time.monotonic()

        logger.info(
            "AI_RESPONSE user=%s conv=%s tools=%s reply_len=%d",
            current_user.get("email"),
            conv_id,
            tools_called,
            len(reply_text),
        )

        return reply_text, conv_id, tools_called

    except Exception as exc:
        logger.warning("AI_GEMINI_FALLBACK error=%s, switching to direct clinical tools", exc)
        reply_text, tools_called = await _fallback_doctor_reply(message, current_user)
        return reply_text, conv_id, tools_called
