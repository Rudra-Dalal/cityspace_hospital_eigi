"""
Read-only AI tool registry.

Each tool is an async callable that receives:
  - validated, sanitised arguments from Gemini (with forbidden auth fields stripped)
  - the authenticated doctor's user document injected by the backend

Tools NEVER receive doctor_id, hospital_id, or any auth field from Gemini directly.
The backend always injects these from the authenticated JWT user.
"""

from __future__ import annotations

import re
from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.cruds import appointment_crud, user_crud
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Security: forbidden fields that Gemini must never control
# ---------------------------------------------------------------------------
_FORBIDDEN_ARGS = frozenset(
    {"doctor_id", "hospital_id", "user_id", "owner_id", "role", "permissions", "_id"}
)


def _strip_forbidden(args: Dict[str, Any]) -> Dict[str, Any]:
    """Remove any auth/identity fields Gemini might have generated."""
    return {k: v for k, v in args.items() if k not in _FORBIDDEN_ARGS}


def _doctor_scope(current_user: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Return (doctor_id, hospital_id) scoped to the authenticated user's role."""
    role = current_user.get("role", "")
    if role == "doctor":
        return str(current_user["_id"]), current_user.get("hospital_id")
    elif role == "hospital_manager":
        return None, current_user.get("hospital_id")
    # super_admin: no scoping
    return None, None


def _serialize_appointment_for_ai(appt: Dict[str, Any], patient_name: Optional[str] = None) -> Dict[str, Any]:
    """Safe appointment dict for Gemini — no ObjectId, no internal fields."""
    result: Dict[str, Any] = {
        "id": str(appt["_id"]),
        "date": appt.get("date"),
        "slot": appt.get("slot"),
        "reason": appt.get("reason"),
        "status": appt.get("status"),
        "symptoms": appt.get("symptoms", []),
        "temperature": appt.get("temperature"),
    }
    if patient_name:
        result["patient_name"] = patient_name
    elif appt.get("patient_name"):
        result["patient_name"] = appt.get("patient_name")
    return result


def _serialize_patient_for_ai(user_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Safe patient dict for Gemini — no password_hash, no internal fields."""
    return {
        "id": str(user_doc["_id"]),
        "name": f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '')}".strip(),
        "email": user_doc.get("email"),
        "mobile": user_doc.get("mobile"),
        "role": user_doc.get("role"),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

async def get_today_schedule(args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Return the authenticated doctor's appointments for today."""
    doctor_id, hospital_id = _doctor_scope(current_user)
    today = datetime.now(timezone.utc).date().isoformat()
    appointments = await appointment_crud.get_appointments_for_date(
        today, doctor_id=doctor_id, hospital_id=hospital_id
    )
    patient_ids = list({a["patient_id"] for a in appointments})
    patients = await user_crud.get_users_by_ids(patient_ids)

    result = []
    for appt in appointments:
        patient = patients.get(appt["patient_id"])
        name = f"{patient['first_name']} {patient['last_name']}" if patient else "Unknown patient"
        result.append(_serialize_appointment_for_ai(appt, name))

    return {
        "date": today,
        "count": len(result),
        "appointments": result,
    }


async def get_schedule_for_date(args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Return appointments for a specific date."""
    safe_args = _strip_forbidden(args)
    date_str = safe_args.get("date", "")

    # Validate date
    if not date_str:
        return {"error": "date parameter is required (YYYY-MM-DD)"}
    try:
        date_cls.fromisoformat(str(date_str))
    except ValueError:
        return {"error": f"Invalid date format: {date_str!r}. Use YYYY-MM-DD."}

    doctor_id, hospital_id = _doctor_scope(current_user)
    appointments = await appointment_crud.get_appointments_for_date(
        str(date_str), doctor_id=doctor_id, hospital_id=hospital_id
    )
    patient_ids = list({a["patient_id"] for a in appointments})
    patients = await user_crud.get_users_by_ids(patient_ids)

    result = []
    for appt in appointments:
        patient = patients.get(appt["patient_id"])
        name = f"{patient['first_name']} {patient['last_name']}" if patient else "Unknown patient"
        result.append(_serialize_appointment_for_ai(appt, name))

    return {
        "date": str(date_str),
        "count": len(result),
        "appointments": result,
    }


async def get_appointment_details(args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Return details for a single appointment the doctor is authorised to access."""
    safe_args = _strip_forbidden(args)
    appointment_id = safe_args.get("appointment_id", "")
    if not appointment_id:
        return {"error": "appointment_id is required"}

    appt = await appointment_crud.get_appointment_by_id(str(appointment_id))
    if not appt:
        return {"error": "Appointment not found."}

    # Authorization: doctor/hospital scoping
    role = current_user.get("role", "")
    if role == "doctor":
        if appt.get("doctor_id") != str(current_user["_id"]):
            return {"error": "You are not authorised to view this appointment."}
    elif role == "hospital_manager":
        if appt.get("hospital_id") != current_user.get("hospital_id"):
            return {"error": "This appointment belongs to a different hospital."}
    # super_admin: no restriction

    patient = await user_crud.get_user_by_id(appt["patient_id"])
    name = f"{patient['first_name']} {patient['last_name']}" if patient else "Unknown patient"
    return _serialize_appointment_for_ai(appt, name)


async def search_my_patients(args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Search patients by name that have appointments with this doctor."""
    safe_args = _strip_forbidden(args)
    query = str(safe_args.get("query", "")).strip()
    if not query or len(query) < 2:
        return {"error": "query must be at least 2 characters"}

    doctor_id, hospital_id = _doctor_scope(current_user)

    # Get all appointments for this doctor to find their patient IDs
    from app.core.database import get_database
    db = get_database()
    appt_query: Dict[str, Any] = {}
    if doctor_id:
        appt_query["doctor_id"] = doctor_id
    if hospital_id:
        appt_query["hospital_id"] = hospital_id

    # Collect unique patient_ids from appointments
    cursor = db.appointments.find(appt_query, {"patient_id": 1})
    patient_ids = list({doc["patient_id"] async for doc in cursor})

    if not patient_ids:
        return {"results": [], "message": "No patients found in your appointment records."}

    # Fetch those patients and filter by name
    patients_map = await user_crud.get_users_by_ids(patient_ids)

    query_lower = query.lower()
    matched = []
    for patient_doc in patients_map.values():
        full_name = f"{patient_doc.get('first_name', '')} {patient_doc.get('last_name', '')}".lower()
        if query_lower in full_name:
            matched.append(_serialize_patient_for_ai(patient_doc))

    return {
        "query": query,
        "count": len(matched),
        "results": matched,
    }


async def get_patient_summary(args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Return a patient summary (only fields that actually exist in the database)."""
    safe_args = _strip_forbidden(args)
    patient_id = str(safe_args.get("patient_id", "")).strip()
    if not patient_id:
        return {"error": "patient_id is required"}

    patient = await user_crud.get_user_by_id(patient_id)
    if not patient:
        return {"error": "Patient not found."}

    # Authorization: verify this patient has appointments with this doctor
    doctor_id, hospital_id = _doctor_scope(current_user)
    from app.core.database import get_database
    db = get_database()
    auth_query: Dict[str, Any] = {"patient_id": str(patient["_id"])}
    if doctor_id:
        auth_query["doctor_id"] = doctor_id
    if hospital_id:
        auth_query["hospital_id"] = hospital_id

    role = current_user.get("role", "")
    if role != "super_admin":
        exists = await db.appointments.find_one(auth_query)
        if not exists:
            return {"error": "Patient not found in your records."}

    # Get appointment count for this doctor
    count_query: Dict[str, Any] = {"patient_id": str(patient["_id"])}
    if doctor_id:
        count_query["doctor_id"] = doctor_id
    if hospital_id:
        count_query["hospital_id"] = hospital_id
    total_appts = await db.appointments.count_documents(count_query)

    summary = _serialize_patient_for_ai(patient)
    summary["total_appointments_with_you"] = total_appts

    return summary


async def get_patient_history(args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a patient's appointment history with this doctor.

    NOTE: CityCare does not store separate clinical history records.
    This returns the patient's appointment records as the available history.
    """
    safe_args = _strip_forbidden(args)
    patient_id = str(safe_args.get("patient_id", "")).strip()
    if not patient_id:
        return {"error": "patient_id is required"}

    patient = await user_crud.get_user_by_id(patient_id)
    if not patient:
        return {"error": "Patient not found."}

    doctor_id, hospital_id = _doctor_scope(current_user)

    # Authorization check
    from app.core.database import get_database
    db = get_database()
    auth_query: Dict[str, Any] = {"patient_id": str(patient["_id"])}
    if doctor_id:
        auth_query["doctor_id"] = doctor_id
    if hospital_id:
        auth_query["hospital_id"] = hospital_id

    role = current_user.get("role", "")
    if role != "super_admin":
        exists = await db.appointments.find_one(auth_query)
        if not exists:
            return {"error": "Patient not found in your records."}

    appointments = await appointment_crud.get_appointments_for_patient(str(patient["_id"]))

    # Filter to only this doctor's scope
    filtered = []
    for appt in appointments:
        if doctor_id and appt.get("doctor_id") != doctor_id:
            continue
        if hospital_id and appt.get("hospital_id") != hospital_id:
            continue
        filtered.append(_serialize_appointment_for_ai(appt))

    patient_info = _serialize_patient_for_ai(patient)

    return {
        "patient": patient_info,
        "appointment_count": len(filtered),
        "appointments": filtered,
        "note": (
            "CityCare stores appointment records only. No separate clinical history "
            "(diagnoses, medications, conditions) is stored in this system."
        ),
    }


async def get_today_statistics(args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Return appointment statistics for today based on actual database records."""
    doctor_id, hospital_id = _doctor_scope(current_user)
    today = datetime.now(timezone.utc).date().isoformat()

    appointments = await appointment_crud.get_appointments_for_date(
        today, doctor_id=doctor_id, hospital_id=hospital_id
    )

    total = len(appointments)
    by_status: Dict[str, int] = {}
    for appt in appointments:
        status = appt.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "date": today,
        "total": total,
        "by_status": by_status,
        "booked": by_status.get("booked", 0),
        "cancelled": by_status.get("cancelled", 0),
    }


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: Dict[str, Any] = {
    "get_today_schedule": get_today_schedule,
    "get_schedule_for_date": get_schedule_for_date,
    "get_appointment_details": get_appointment_details,
    "search_my_patients": search_my_patients,
    "get_patient_summary": get_patient_summary,
    "get_patient_history": get_patient_history,
    "get_today_statistics": get_today_statistics,
}

# Human-readable labels shown in the UI
TOOL_LABELS: Dict[str, str] = {
    "get_today_schedule": "Checking today's schedule",
    "get_schedule_for_date": "Checking appointments for date",
    "get_appointment_details": "Looking up appointment details",
    "search_my_patients": "Looking up patient records",
    "get_patient_summary": "Reviewing patient information",
    "get_patient_history": "Reviewing patient history",
    "get_today_statistics": "Calculating today's statistics",
}


async def execute_tool(
    tool_name: str,
    args: Dict[str, Any],
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a registered tool.

    Security: strips forbidden auth fields from Gemini-supplied args before calling the tool.
    Returns an error dict if the tool is unknown.
    """
    if tool_name not in TOOL_REGISTRY:
        logger.warning("AI attempted to call unknown tool: %s", tool_name)
        return {"error": f"Unknown tool: {tool_name!r}. Only registered read-only tools are available."}

    handler = TOOL_REGISTRY[tool_name]
    clean_args = _strip_forbidden(args or {})
    logger.info("AI_TOOL_CALL tool=%s args_keys=%s user=%s", tool_name, list(clean_args.keys()), current_user.get("email"))
    try:
        result = await handler(clean_args, current_user)
        return result
    except Exception as exc:
        logger.exception("Tool %s failed: %s", tool_name, exc)
        return {"error": f"Tool {tool_name!r} failed. Please try again."}
