"""Public discovery flow handlers for hospitals, doctors, and facilities."""

from typing import Any, Dict, List, Optional
from app.services.patient_discovery_service import (
    list_active_hospitals,
    get_hospital_details,
    list_active_doctors,
)
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.keyboards import (
    hospitals_keyboard,
    specializations_keyboard,
    doctors_keyboard,
    main_menu_keyboard,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def show_hospitals(adapter: TelegramAdapter, chat_id: int) -> None:
    """Display active hospital branches."""
    hospitals = await list_active_hospitals()
    if not hospitals:
        await adapter.send_message(
            chat_id=chat_id,
            text="🏥 *CityCare Hospital Branches*\n\nNo active hospital branches are currently available\\.",
            reply_markup=main_menu_keyboard(),
        )
        return

    text_lines = ["🏥 *CityCare Hospital Branches*\n", "Select a hospital to view facilities or start booking:\n"]
    for h in hospitals:
        name = escape_markdown(h.get("name"))
        city = escape_markdown(h.get("city"))
        phone = escape_markdown(h.get("contact_phone"))
        hours = escape_markdown(h.get("working_hours"))
        text_lines.append(f"• *{name}* ({city})\n  📞 {phone} | 🕒 {hours}")

    await adapter.send_message(
        chat_id=chat_id,
        text="\n".join(text_lines),
        reply_markup=hospitals_keyboard(hospitals, callback_prefix="view:hosp:"),
    )


async def show_hospital_detail(adapter: TelegramAdapter, chat_id: int, hospital_id: str) -> None:
    """Display detailed info for a single hospital."""
    hospital = await get_hospital_details(hospital_id)
    if not hospital:
        await adapter.send_message(chat_id=chat_id, text="Hospital branch not found or inactive\\.")
        return

    name = escape_markdown(hospital.get("name"))
    address = escape_markdown(hospital.get("address"))
    city = escape_markdown(hospital.get("city"))
    state = escape_markdown(hospital.get("state"))
    phone = escape_markdown(hospital.get("contact_phone"))
    email = escape_markdown(hospital.get("contact_email"))
    hours = escape_markdown(hospital.get("working_hours"))

    facilities = hospital.get("facilities", [])
    services = hospital.get("services", [])

    fac_str = ", ".join(escape_markdown(f) for f in facilities) if facilities else "General Inpatient, Emergency"
    srv_str = ", ".join(escape_markdown(s) for s in services) if services else "General Medicine, Diagnostics"

    msg = f"""🏥 *{name}*

📍 *Address:* {address}, {city}, {state}
📞 *Contact Phone:* {phone}
✉️ *Email:* {email}
🕒 *Operating Hours:* {hours}

🏢 *Facilities:*
{fac_str}

🩺 *Clinical Services:*
{srv_str}
"""
    await adapter.send_message(
        chat_id=chat_id,
        text=msg,
        reply_markup=main_menu_keyboard(),
    )


async def show_doctors(adapter: TelegramAdapter, chat_id: int, specialization: Optional[str] = None) -> None:
    """Display specialist doctors."""
    doctors = await list_active_doctors(specialization=specialization)
    if not doctors:
        spec_text = f" in *{escape_markdown(specialization)}*" if specialization else ""
        await adapter.send_message(
            chat_id=chat_id,
            text=f"👨‍⚕️ *Specialist Doctors*\n\nNo doctors found{spec_text}\\.",
            reply_markup=main_menu_keyboard(),
        )
        return

    title_spec = f" — {escape_markdown(specialization)}" if specialization else ""
    text_lines = [f"👨‍⚕️ *CityCare Specialist Doctors{title_spec}*\n"]
    for d in doctors:
        name = escape_markdown(f"Dr. {d.get('first_name')} {d.get('last_name')}")
        spec = escape_markdown(d.get("specialization"))
        qual = escape_markdown(d.get("qualification"))
        h_name = escape_markdown(d.get("hospital_name") or "Central Branch")
        fee = d.get("consultation_fee")
        fee_str = f" | ₹{fee:.0f}" if fee else ""
        days = ", ".join(d.get("available_days", [])[:3])
        days_esc = escape_markdown(days)

        text_lines.append(f"• *{name}* ({spec})\n  🎓 {qual} | 🏥 {h_name}{fee_str}\n  📅 Days: {days_esc}...")

    await adapter.send_message(
        chat_id=chat_id,
        text="\n".join(text_lines),
        reply_markup=doctors_keyboard(doctors[:10]),
    )


async def show_specializations(adapter: TelegramAdapter, chat_id: int) -> None:
    """Display available specializations."""
    doctors = await list_active_doctors()
    specs = sorted(list({d.get("specialization") for d in doctors if d.get("specialization")}))
    if not specs:
        specs = ["Cardiology", "Dermatology", "General Medicine", "Neurology", "Orthopedics", "Pediatrics"]

    await adapter.send_message(
        chat_id=chat_id,
        text="🩺 *Select Medical Specialization*\n\nChoose a clinical department to view available specialist doctors:",
        reply_markup=specializations_keyboard(specs),
    )
