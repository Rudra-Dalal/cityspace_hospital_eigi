"""Inline and reply keyboard builders for Telegram Patient Assistant."""

from typing import Any, Dict, List, Optional
from telegram_gateway.adapter import escape_markdown


def build_inline_keyboard(buttons: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    """Format inline keyboard markup dictionary."""
    return {"inline_keyboard": buttons}


def main_menu_keyboard(is_verified: bool = False) -> Dict[str, Any]:
    """Primary navigation menu for patients."""
    if is_verified:
        buttons = [
            [
                {"text": "🏥 Hospital Branches", "callback_data": "nav:hospitals"},
                {"text": "👨‍⚕️ Specialists", "callback_data": "nav:doctors"},
            ],
            [
                {"text": "📅 Book Appointment", "callback_data": "nav:book"},
                {"text": "📋 My Appointments", "callback_data": "nav:my_appointments"},
            ],
            [
                {"text": "💊 My Prescriptions", "callback_data": "nav:my_prescriptions"},
                {"text": "ℹ️ Facilities & Info", "callback_data": "nav:facilities"},
            ],
            [
                {"text": "❓ Help & Guidelines", "callback_data": "nav:help"},
            ],
        ]
    else:
        buttons = [
            [
                {"text": "🏥 Hospital Branches", "callback_data": "nav:hospitals"},
                {"text": "👨‍⚕️ Specialists", "callback_data": "nav:doctors"},
            ],
            [
                {"text": "🔗 Link Existing Account", "callback_data": "nav:link"},
                {"text": "📝 New Patient Signup", "callback_data": "nav:register"},
            ],
            [
                {"text": "ℹ️ Facilities & Info", "callback_data": "nav:facilities"},
                {"text": "❓ Help & Guidelines", "callback_data": "nav:help"},
            ],
        ]
    return build_inline_keyboard(buttons)


def hospitals_keyboard(hospitals: List[Dict[str, Any]], callback_prefix: str = "bk:hosp:") -> Dict[str, Any]:
    """List of hospital branches for selection."""
    buttons = []
    for h in hospitals:
        city_str = f" ({h.get('city')})" if h.get("city") else ""
        label = f"🏥 {h.get('name')}{city_str}"
        buttons.append([{"text": label, "callback_data": f"{callback_prefix}{h.get('id')}"}])
    buttons.append([{"text": "❌ Cancel", "callback_data": "bk:cancel"}])
    return build_inline_keyboard(buttons)


def specializations_keyboard(specializations: List[str], hospital_id: Optional[str] = None) -> Dict[str, Any]:
    """List of medical specializations for filtering."""
    buttons = []
    h_prefix = f"h:{hospital_id}:" if hospital_id else "h:all:"
    for spec in specializations:
        buttons.append([{"text": f"🩺 {spec}", "callback_data": f"bk:spec:{h_prefix}{spec}"}])
    buttons.append([{"text": "👨‍⚕️ View All Doctors", "callback_data": f"bk:spec:{h_prefix}ALL"}])
    buttons.append([{"text": "❌ Cancel", "callback_data": "bk:cancel"}])
    return build_inline_keyboard(buttons)


def doctors_keyboard(doctors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """List of doctors for selection."""
    buttons = []
    for d in doctors:
        spec_str = f" — {d.get('specialization')}" if d.get("specialization") else ""
        label = f"👨‍⚕️ Dr. {d.get('first_name')} {d.get('last_name')}{spec_str}"
        buttons.append([{"text": label, "callback_data": f"bk:doc:{d.get('id')}"}])
    buttons.append([{"text": "❌ Cancel", "callback_data": "bk:cancel"}])
    return build_inline_keyboard(buttons)


def dates_keyboard(dates: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    List of dates for booking.
    dates: list of {'date': 'YYYY-MM-DD', 'label': 'Mon, Aug 25'}
    """
    buttons = []
    # Display in pairs of 2 per row
    row = []
    for item in dates:
        row.append({"text": item["label"], "callback_data": f"bk:date:{item['date']}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "❌ Cancel", "callback_data": "bk:cancel"}])
    return build_inline_keyboard(buttons)


def slots_keyboard(slots: List[str]) -> Dict[str, Any]:
    """List of available appointment slots in rows of 3."""
    buttons = []
    row = []
    for slot in slots:
        row.append({"text": f"⏰ {slot}", "callback_data": f"bk:slot:{slot}"})
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "❌ Cancel", "callback_data": "bk:cancel"}])
    return build_inline_keyboard(buttons)


def confirmation_keyboard() -> Dict[str, Any]:
    """Explicit confirmation buttons before creating appointment."""
    buttons = [
        [
            {"text": "✅ Confirm Booking", "callback_data": "bk:confirm"},
            {"text": "❌ Cancel", "callback_data": "bk:cancel"},
        ]
    ]
    return build_inline_keyboard(buttons)


def consent_keyboard() -> Dict[str, Any]:
    """Consent confirmation button for registration."""
    buttons = [
        [
            {"text": "✅ I Agree & Continue", "callback_data": "reg:consent_yes"},
            {"text": "❌ Cancel", "callback_data": "reg:consent_no"},
        ]
    ]
    return build_inline_keyboard(buttons)


def registration_summary_keyboard() -> Dict[str, Any]:
    """Confirmation keyboard before final patient creation."""
    buttons = [
        [
            {"text": "✅ Confirm Registration", "callback_data": "reg:confirm"},
            {"text": "✏️ Edit Details", "callback_data": "reg:edit"},
        ],
        [
            {"text": "❌ Cancel", "callback_data": "reg:cancel"},
        ],
    ]
    return build_inline_keyboard(buttons)


def quick_departments_keyboard(specializations: Optional[List[str]] = None) -> Dict[str, Any]:
    """Quick selection shortcuts for top clinical departments."""
    specs = specializations or ["Cardiology", "Dermatology", "General Medicine", "Pediatrics", "Orthopedics"]
    buttons = []
    row = []
    for s in specs:
        row.append({"text": f"🩺 {s}", "callback_data": f"bk:spec:h:all:{s}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "👨‍⚕️ View All Doctors", "callback_data": "nav:doctors"}])
    return build_inline_keyboard(buttons)

