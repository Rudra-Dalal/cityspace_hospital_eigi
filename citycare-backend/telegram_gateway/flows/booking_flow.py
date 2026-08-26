"""Deterministic appointment booking state machine flow handler."""

from datetime import date as date_cls, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import re
import zoneinfo

from app.core.config import get_settings
from app.cruds import user_crud
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
from telegram_gateway.adapter import TelegramAdapter, escape_markdown
from telegram_gateway.keyboards import (
    build_inline_keyboard,
    hospitals_keyboard,
    specializations_keyboard,
    doctors_keyboard,
    dates_keyboard,
    slots_keyboard,
    confirmation_keyboard,
    main_menu_keyboard,
)
from telegram_gateway.models import TelegramFlowType, TelegramSession
from telegram_gateway.session_manager import SessionManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def start_booking_flow(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    patient: Optional[Dict[str, Any]],
) -> None:
    """Initiate booking flow step 1: Hospital branch selection or conversational registration for unregistered patients."""
    if not patient or not session.patient_id:
        flow_data = dict(session.flow_data or {})
        flow_data["pending_booking"] = {"start_booking": True}
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.REGISTRATION.value,
            flow_step="enter_name",
            flow_data=flow_data,
        )
        await adapter.send_message(
            chat_id=chat_id,
            text=(
                "It looks like you don't have a CityCare patient profile yet\\. "
                "I can help you register first, and then we can continue with your appointment\\.\n\n"
                "What's your full name?"
            ),
        )
        return

    hospitals = await list_active_hospitals()
    if not hospitals:
        await adapter.send_message(
            chat_id=chat_id,
            text="🏥 No active hospital branches are currently available for booking\\.",
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return

    await SessionManager.update_flow(
        session_key=session.session_key,
        current_flow=TelegramFlowType.BOOKING.value,
        flow_step="select_hospital",
        flow_data={},
    )

    await adapter.send_message(
        chat_id=chat_id,
        text="📅 *Step 1/5: Select Hospital Branch*\n\nChoose the clinic or hospital location for your visit:",
        reply_markup=hospitals_keyboard(hospitals),
    )


async def handle_booking_text_message(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    patient: Optional[Dict[str, Any]],
    text: str,
) -> bool:
    """Handle natural text input at any step of the booking flow."""
    if session.current_flow != TelegramFlowType.BOOKING.value:
        return False

    from telegram_gateway.assistant import (
        parse_relative_date,
        parse_time_slot,
        SYMPTOM_SPECIALIZATION_MAP,
    )

    clean_text = text.strip()
    lower_text = clean_text.lower()
    flow_step = session.flow_step
    flow_data = dict(session.flow_data or {})

    # 1. Check for cancel / changed mind
    if re.search(r"\b(changed my mind|forget it|forget that|nevermind|start over|cancel)\b", lower_text):
        await SessionManager.clear_flow(session.session_key)
        await adapter.send_message(
            chat_id=chat_id,
            text="❌ *Booking Cancelled*\n\nYour active booking session has been cleared\\. How can CityCare assist you today?",
            reply_markup=main_menu_keyboard(is_verified=bool(patient)),
        )
        return True

    # 2. Check for switching doctor
    if re.search(r"\b(different doctor|another doctor|change doctor|switch doctor)\b", lower_text):
        flow_data.pop("doctor_id", None)
        flow_data.pop("doctor_name", None)
        flow_data.pop("slot", None)
        spec = flow_data.get("specialization")
        doctors = await list_active_doctors(specialization=spec)
        if not doctors:
            doctors = await list_active_doctors()
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="select_doctor",
            flow_data=flow_data,
        )
        await adapter.send_message(
            chat_id=chat_id,
            text="No problem\\! Which doctor or department would you prefer instead?",
            reply_markup=doctors_keyboard(doctors[:6]),
        )
        return True

    # 3. Handle step: select_hospital
    if flow_step == "select_hospital":
        hospitals = await list_active_hospitals()
        matched_hosp = None
        for h in hospitals:
            if lower_text in h.get("name", "").lower() or (h.get("city") and lower_text in h.get("city", "").lower()):
                matched_hosp = h
                break
        if matched_hosp:
            flow_data["hospital_id"] = matched_hosp["id"]
            flow_data["hospital_name"] = matched_hosp.get("name")
            flow_data["hospital_city"] = matched_hosp.get("city")
            doctors = await list_active_doctors(hospital_id=matched_hosp["id"])
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="select_doctor",
                flow_data=flow_data,
            )
            h_esc = escape_markdown(matched_hosp.get("name"))
            await adapter.send_message(
                chat_id=chat_id,
                text=f"🏥 *Branch:* {h_esc}\n\nWhich doctor would you like to see?",
                reply_markup=doctors_keyboard(doctors[:6]),
            )
            return True

    # 4. Handle step: select_doctor
    if flow_step in ("select_doctor", "select_specialization") or not flow_data.get("doctor_id"):
        # Check doctor name
        doctors = await list_active_doctors()
        matched_doc = None
        for d in doctors:
            full = f"{d.get('first_name', '')} {d.get('last_name', '')}".lower()
            last = d.get('last_name', '').lower()
            if lower_text in full or last in lower_text or lower_text in last:
                matched_doc = d
                break
        if matched_doc:
            flow_data["doctor_id"] = matched_doc["id"]
            flow_data["doctor_name"] = f"Dr. {matched_doc.get('first_name')} {matched_doc.get('last_name')}"
            flow_data["hospital_id"] = matched_doc.get("hospital_id")
            flow_data["hospital_name"] = matched_doc.get("hospital_name") or "Central Branch"
            flow_data["specialization"] = matched_doc.get("specialization") or flow_data.get("specialization")

            # Check if date was also mentioned in text
            d_parsed = parse_relative_date(clean_text)
            if d_parsed:
                flow_data["date"] = d_parsed

            # Move to select_date or select_slot
            if flow_data.get("date"):
                # Check slot availability
                avail = await get_doctor_availability(matched_doc["id"], flow_data["date"])
                open_slots = avail.get("available_slots", [])
                await SessionManager.update_flow(
                    session_key=session.session_key,
                    current_flow=TelegramFlowType.BOOKING.value,
                    flow_step="select_slot",
                    flow_data=flow_data,
                )
                d_esc = escape_markdown(flow_data["doctor_name"])
                date_esc = escape_markdown(flow_data["date"])
                await adapter.send_message(
                    chat_id=chat_id,
                    text=f"*{d_esc}* has open slots on *{date_esc}*\\. Which time slot works for you?",
                    reply_markup=slots_keyboard(open_slots[:12]),
                )
                return True
            else:
                today = get_current_date_in_tz()
                dates = [
                    {"date": today.isoformat(), "label": f"Today ({today.strftime('%a')})"},
                    {"date": (today + timedelta(days=1)).isoformat(), "label": f"Tomorrow ({(today + timedelta(days=1)).strftime('%a')})"},
                    {"date": (today + timedelta(days=2)).isoformat(), "label": (today + timedelta(days=2)).strftime('%a, %b %d')},
                ]
                await SessionManager.update_flow(
                    session_key=session.session_key,
                    current_flow=TelegramFlowType.BOOKING.value,
                    flow_step="select_date",
                    flow_data=flow_data,
                )
                d_esc = escape_markdown(flow_data["doctor_name"])
                await adapter.send_message(
                    chat_id=chat_id,
                    text=f"Great\\! You've selected *{d_esc}*\\. Which date would you prefer for your consultation?",
                    reply_markup=dates_keyboard(dates),
                )
                return True

    # 5. Handle step: select_date
    if flow_step == "select_date" or (flow_data.get("doctor_id") and not flow_data.get("date")):
        d_parsed = parse_relative_date(clean_text)
        if d_parsed:
            flow_data["date"] = d_parsed
            doc_id = flow_data.get("doctor_id")
            avail = await get_doctor_availability(doc_id, d_parsed)
            open_slots = avail.get("available_slots", [])
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="select_slot",
                flow_data=flow_data,
            )
            d_esc = escape_markdown(flow_data.get("doctor_name", "Doctor"))
            date_esc = escape_markdown(d_parsed)
            if open_slots:
                await adapter.send_message(
                    chat_id=chat_id,
                    text=f"Here are the available slots for *{d_esc}* on *{date_esc}*\\. Which time works best for you?",
                    reply_markup=slots_keyboard(open_slots[:12]),
                )
            else:
                await adapter.send_message(
                    chat_id=chat_id,
                    text=f"Unfortunately *{d_esc}* has no open slots on *{date_esc}*\\. Could you choose a different date?",
                    reply_markup=dates_keyboard([]),
                )
            return True

    # 6. Handle step: select_slot
    if flow_step == "select_slot" or (flow_data.get("doctor_id") and flow_data.get("date") and not flow_data.get("slot")):
        s_parsed = parse_time_slot(clean_text)
        if s_parsed:
            flow_data["slot"] = s_parsed
            await SessionManager.update_flow(
                session_key=session.session_key,
                current_flow=TelegramFlowType.BOOKING.value,
                flow_step="enter_reason",
                flow_data=flow_data,
            )
            d_esc = escape_markdown(flow_data.get("doctor_name", "your doctor"))
            slot_esc = escape_markdown(s_parsed)
            await adapter.send_message(
                chat_id=chat_id,
                text=f"Got it\\! {slot_esc} with *{d_esc}*\\. What symptoms or reason for visit should we note for the doctor?",
            )
            return True

    # 7. Handle step: enter_reason
    if flow_step == "enter_reason":
        reason_clean = clean_text
        if not reason_clean:
            await adapter.send_message(chat_id=chat_id, text="Please enter a valid reason for consultation\\.")
            return True

        flow_data["reason"] = reason_clean
        doc_id = flow_data.get("doctor_id")
        if doc_id and not flow_data.get("hospital_name"):
            doc = await get_doctor_details(doc_id)
            if doc:
                if doc.get("hospital_id") and not flow_data.get("hospital_id"):
                    flow_data["hospital_id"] = str(doc["hospital_id"])
                if doc.get("hospital_name"):
                    flow_data["hospital_name"] = doc["hospital_name"]

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="confirm_booking",
            flow_data=flow_data,
        )

        h_name = escape_markdown(flow_data.get("hospital_name", "Central Clinic Branch"))
        d_name = escape_markdown(flow_data.get("doctor_name", "Specialist Physician"))
        date_val = escape_markdown(flow_data.get("date", ""))
        slot_val = escape_markdown(flow_data.get("slot", ""))
        reason_esc = escape_markdown(reason_clean)

        summary_text = f"""📋 *Appointment Summary*

🏥 *Hospital:* {h_name}
👨‍⚕️ *Doctor:* {d_name}
📅 *Date:* {date_val}
⏰ *Slot:* {slot_val}
📝 *Reason:* {reason_esc}

Please confirm your booking details:"""

        await adapter.send_message(
            chat_id=chat_id,
            text=summary_text,
            reply_markup=confirmation_keyboard(),
        )
        return True

    # 8. Handle step: confirm_booking
    if flow_step == "confirm_booking":
        if re.search(r"^\b(yes|confirm|proceed|looks good|correct|agree|sure)\b", lower_text):
            # Book appointment
            if not patient:
                # Unregistered patient: transition to registration holding pending booking
                flow_data["pending_booking"] = {
                    "doctor_id": flow_data.get("doctor_id"),
                    "doctor_name": flow_data.get("doctor_name"),
                    "hospital_id": flow_data.get("hospital_id"),
                    "hospital_name": flow_data.get("hospital_name"),
                    "date": flow_data.get("date"),
                    "slot": flow_data.get("slot"),
                    "reason": flow_data.get("reason"),
                }
                await SessionManager.update_flow(
                    session_key=session.session_key,
                    current_flow=TelegramFlowType.REGISTRATION.value,
                    flow_step="enter_name",
                    flow_data=flow_data,
                )
                await adapter.send_message(
                    chat_id=chat_id,
                    text=(
                        "It looks like you don't have a patient profile with CityCare yet\\. "
                        "I can help you register first, and then we can continue with your appointment\\.\n\n"
                        "What is your full name?"
                    ),
                )
                return True

            try:
                res = await book_patient_appointment(
                    patient=patient,
                    date_str=flow_data["date"],
                    slot=flow_data["slot"],
                    reason=flow_data.get("reason", "Consultation"),
                    hospital_id=flow_data.get("hospital_id"),
                    doctor_id=flow_data.get("doctor_id"),
                )
                await SessionManager.clear_flow(session.session_key)
                appt_id = escape_markdown(res.get("id", ""))
                d_name = escape_markdown(flow_data.get("doctor_name", "Specialist Doctor"))
                h_name = escape_markdown(flow_data.get("hospital_name", "Central Clinic"))
                confirm_text = f"""✅ *Appointment Confirmed!*

Your appointment with *{d_name}* at *{h_name}* is booked\\.

📅 *Date:* {escape_markdown(flow_data['date'])}
⏰ *Time:* {escape_markdown(flow_data['slot'])}
📝 *Reason:* {escape_markdown(flow_data.get('reason', 'Consultation'))}
🆔 *Reference:* `{appt_id}`

_Please arrive 15 minutes before your scheduled appointment time\\._"""
                await adapter.send_message(
                    chat_id=chat_id,
                    text=confirm_text,
                    reply_markup=main_menu_keyboard(is_verified=True),
                )
                return True
            except SlotConflictError:
                await adapter.send_message(
                    chat_id=chat_id,
                    text="⚠️ *Slot Conflict*\n\nThat slot was just booked by another patient\\. Please choose another available slot\\.",
                    reply_markup=main_menu_keyboard(is_verified=True),
                )
                return True
            except BookingError as exc:
                await adapter.send_message(
                    chat_id=chat_id,
                    text=f"❌ *Booking Error:* {escape_markdown(str(exc))}",
                    reply_markup=main_menu_keyboard(is_verified=True),
                )
                return True

    return False


async def handle_booking_callback(
    adapter: TelegramAdapter,
    chat_id: int,
    session: TelegramSession,
    patient: Optional[Dict[str, Any]],
    callback_data: str,
    callback_query_id: str,
) -> None:
    """Process inline keyboard callbacks for the booking state machine."""
    settings = get_settings()
    tz_name = settings.telegram_timezone

    if callback_data == "bk:cancel":
        await SessionManager.clear_flow(session.session_key)
        await adapter.answer_callback_query(callback_query_id, text="Booking cancelled")
        await adapter.send_message(
            chat_id=chat_id,
            text="❌ *Booking Cancelled*\n\nYour active booking session has been cleared\\.",
            reply_markup=main_menu_keyboard(is_verified=bool(patient)),
        )
        return

    # Verify patient authentication
    if not patient or not session.patient_id:
        await adapter.answer_callback_query(callback_query_id, text="Please link your account first", show_alert=True)
        return

    flow_data = dict(session.flow_data or {})

    # 1. Hospital Selected -> Show Specialization or Doctors
    if callback_data.startswith("bk:hosp:"):
        hosp_id = callback_data.split("bk:hosp:")[1].strip()
        hospital = await get_hospital_details(hosp_id)
        if not hospital:
            await adapter.answer_callback_query(callback_query_id, text="Selected hospital is inactive", show_alert=True)
            return

        flow_data["hospital_id"] = hosp_id
        flow_data["hospital_name"] = hospital.get("name")
        flow_data["hospital_city"] = hospital.get("city")

        doctors = await list_active_doctors(hospital_id=hosp_id)
        specs = sorted(list({d.get("specialization") for d in doctors if d.get("specialization")}))

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="select_doctor",
            flow_data=flow_data,
        )
        await adapter.answer_callback_query(callback_query_id)

        h_name_esc = escape_markdown(hospital.get("name"))
        if specs:
            await adapter.send_message(
                chat_id=chat_id,
                text=f"🏥 *Branch:* {h_name_esc}\n\n*Step 2/5: Select Department or Specialist*",
                reply_markup=specializations_keyboard(specs, hospital_id=hosp_id),
            )
        else:
            await adapter.send_message(
                chat_id=chat_id,
                text=f"🏥 *Branch:* {h_name_esc}\n\n*Step 2/5: Select Specialist Doctor*",
                reply_markup=doctors_keyboard(doctors),
            )
        return

    # 2. Specialization Selected -> Filter Doctors
    if callback_data.startswith("bk:spec:"):
        parts = callback_data.split(":")
        # Format: bk:spec:h:<hid>:<spec>
        hid = parts[3] if len(parts) > 3 and parts[2] == "h" else flow_data.get("hospital_id")
        spec = parts[4] if len(parts) > 4 else parts[-1]
        spec_filter = None if spec == "ALL" else spec

        doctors = await list_active_doctors(specialization=spec_filter, hospital_id=hid if hid != "all" else None)
        if not doctors:
            await adapter.answer_callback_query(callback_query_id, text="No doctors available in this department", show_alert=True)
            return

        flow_data["specialization"] = spec_filter
        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="select_doctor",
            flow_data=flow_data,
        )
        await adapter.answer_callback_query(callback_query_id)

        spec_label = f" ({escape_markdown(spec_filter)})" if spec_filter else ""
        await adapter.send_message(
            chat_id=chat_id,
            text=f"👨‍⚕️ *Step 2/5: Select Doctor{spec_label}*",
            reply_markup=doctors_keyboard(doctors),
        )
        return

    # 3. Doctor Selected -> Show Next 7 Days
    if callback_data.startswith("bk:doc:"):
        doc_id = callback_data.split("bk:doc:")[1].strip()
        doctor = await get_doctor_details(doc_id)
        if not doctor:
            await adapter.answer_callback_query(callback_query_id, text="Doctor not found or inactive", show_alert=True)
            return

        flow_data["doctor_id"] = doc_id
        flow_data["doctor_name"] = f"Dr. {doctor.get('first_name')} {doctor.get('last_name')}".strip()
        flow_data["doctor_spec"] = doctor.get("specialization")

        # Auto-populate hospital details from doctor profile
        if doctor.get("hospital_id"):
            flow_data["hospital_id"] = str(doctor["hospital_id"])
            if doctor.get("hospital_name"):
                flow_data["hospital_name"] = doctor["hospital_name"]
            if doctor.get("hospital_city"):
                flow_data["hospital_city"] = doctor["hospital_city"]
        elif not flow_data.get("hospital_id"):
            all_hosps = await list_active_hospitals()
            if all_hosps:
                flow_data["hospital_id"] = str(all_hosps[0]["id"])
                flow_data["hospital_name"] = all_hosps[0].get("name")
                flow_data["hospital_city"] = all_hosps[0].get("city")

        # Generate upcoming 7 booking dates in hospital timezone
        today = get_current_date_in_tz(tz_name)
        dates_list = []
        for i in range(7):
            d = today.fromordinal(today.toordinal() + i)
            d_str = d.isoformat()
            label = d.strftime("%a, %b %d")
            dates_list.append({"date": d_str, "label": label})

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="select_date",
            flow_data=flow_data,
        )
        await adapter.answer_callback_query(callback_query_id)

        d_name_esc = escape_markdown(flow_data["doctor_name"])
        await adapter.send_message(
            chat_id=chat_id,
            text=f"👨‍⚕️ *Doctor:* {d_name_esc}\n\n*Step 3/5: Select Appointment Date*",
            reply_markup=dates_keyboard(dates_list),
        )
        return

    # 4. Date Selected -> Fetch Live Doctor Availability & Show Slots
    if callback_data.startswith("bk:date:"):
        date_str = callback_data.split("bk:date:")[1].strip()
        doc_id = flow_data.get("doctor_id")
        if not doc_id:
            await adapter.answer_callback_query(callback_query_id, text="Please select doctor first", show_alert=True)
            return

        try:
            avail = await get_doctor_availability(doc_id, date_str, tz_name=tz_name)
        except ValueError as exc:
            await adapter.answer_callback_query(callback_query_id, text=str(exc), show_alert=True)
            return

        if not avail.get("is_available") or not avail.get("available_slots"):
            weekday = avail.get("weekday", "that day")
            await adapter.answer_callback_query(
                callback_query_id,
                text=f"Doctor is not available on {weekday} ({date_str}). Please select another date.",
                show_alert=True,
            )
            return

        flow_data["date"] = date_str
        flow_data["weekday"] = avail.get("weekday")
        slots = avail.get("available_slots", [])

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="select_slot",
            flow_data=flow_data,
        )
        await adapter.answer_callback_query(callback_query_id)

        d_name_esc = escape_markdown(flow_data.get("doctor_name"))
        await adapter.send_message(
            chat_id=chat_id,
            text=(
                f"👨‍⚕️ *Doctor:* {d_name_esc}\n"
                f"📅 *Date:* {escape_markdown(date_str)} ({escape_markdown(avail.get('weekday'))})\n\n"
                f"*Step 4/5: Select Time Slot*"
            ),
            reply_markup=slots_keyboard(slots),
        )
        return

    # 5. Slot Selected -> Prompt Reason for Consultation
    if callback_data.startswith("bk:slot:"):
        slot_str = callback_data.split("bk:slot:")[1].strip()
        flow_data["slot"] = slot_str

        await SessionManager.update_flow(
            session_key=session.session_key,
            current_flow=TelegramFlowType.BOOKING.value,
            flow_step="enter_reason",
            flow_data=flow_data,
        )
        await adapter.answer_callback_query(callback_query_id)

        await adapter.send_message(
            chat_id=chat_id,
            text=(
                "📝 *Step 5/5: Reason for Visit*\n\n"
                "Please type a brief reason or symptoms for the appointment \\(e\\.g\\. _fever and severe headache since 2 days_\\):"
            ),
        )
        return

    # 6. Explicit Confirmation Click
    if callback_data == "bk:confirm":
        # Final server-side booking submission
        doc_id = flow_data.get("doctor_id")
        hosp_id = flow_data.get("hospital_id")
        date_val = flow_data.get("date")
        slot_val = flow_data.get("slot")
        reason_val = flow_data.get("reason", "Consultation")

        # Fallback: auto-resolve hospital if doctor is known
        if doc_id and not hosp_id:
            doctor = await get_doctor_details(doc_id)
            if doctor and doctor.get("hospital_id"):
                hosp_id = str(doctor["hospital_id"])
                flow_data["hospital_id"] = hosp_id
                if doctor.get("hospital_name"):
                    flow_data["hospital_name"] = doctor["hospital_name"]
            else:
                all_hosps = await list_active_hospitals()
                if all_hosps:
                    hosp_id = str(all_hosps[0]["id"])
                    flow_data["hospital_id"] = hosp_id
                    flow_data["hospital_name"] = all_hosps[0].get("name")

        if not patient and session.patient_id:
            patient = await user_crud.get_user_by_id(session.patient_id)

        if not doc_id or not hosp_id or not date_val or not slot_val:
            logger.warning("Incomplete booking details: %s", flow_data)
            await adapter.answer_callback_query(callback_query_id, text="Incomplete booking details. Please restart.", show_alert=True)
            return

        try:
            appt = await book_patient_appointment(
                patient=patient,
                date_str=date_val,
                slot=slot_val,
                reason=reason_val,
                hospital_id=hosp_id,
                doctor_id=doc_id,
                temperature=flow_data.get("temperature"),
                symptoms=flow_data.get("symptoms", []),
                tz_name=tz_name,
            )
        except SlotConflictError:
            await adapter.answer_callback_query(
                callback_query_id,
                text="This slot was just booked by another patient. Please choose another slot.",
                show_alert=True,
            )
            # Re-fetch availability and show remaining slots
            avail = await get_doctor_availability(doc_id, date_val, tz_name=tz_name)
            await adapter.send_message(
                chat_id=chat_id,
                text="⚠️ *Slot No Longer Available*\n\nPlease select an alternative slot:",
                reply_markup=slots_keyboard(avail.get("available_slots", [])),
            )
            return
        except BookingError as exc:
            await adapter.answer_callback_query(callback_query_id, text=str(exc), show_alert=True)
            return

        # Success: clear active flow
        await SessionManager.clear_flow(session.session_key)
        await adapter.answer_callback_query(callback_query_id, text="Appointment Confirmed!")

        appt_id = escape_markdown(appt.get("id"))
        h_name = escape_markdown(appt.get("hospital_name") or flow_data.get("hospital_name"))
        d_name = escape_markdown(appt.get("doctor_name") or flow_data.get("doctor_name"))
        date_esc = escape_markdown(appt.get("date"))
        slot_esc = escape_markdown(appt.get("slot"))
        reason_esc = escape_markdown(appt.get("reason"))

        confirmation_msg = f"""🎉 *Appointment Confirmed!*

📋 *Reference ID:* `{appt_id}`
🏥 *Hospital:* {h_name}
👨‍⚕️ *Doctor:* {d_name}
📅 *Date:* {date_esc}
⏰ *Time:* {slot_esc}
📝 *Reason:* {reason_esc}
📌 *Status:* Booked

_Please arrive 15 minutes before your scheduled appointment time\\._"""

        await adapter.send_message(
            chat_id=chat_id,
            text=confirmation_msg,
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return



async def show_patient_appointments(
    adapter: TelegramAdapter,
    chat_id: int,
    patient: Optional[Dict[str, Any]],
) -> None:
    """Display scheduled and past appointments for verified patient."""
    if not patient:
        await adapter.send_message(
            chat_id=chat_id,
            text="🔒 Please link your account with /link or register with /register to view your appointments.",
            reply_markup=main_menu_keyboard(is_verified=False),
        )
        return

    patient_id = str(patient["_id"])
    appts = await get_patient_appointments(patient_id)

    if not appts:
        await adapter.send_message(
            chat_id=chat_id,
            text="📋 *My Appointments*\n\nYou do not have any appointments scheduled\\.\n\nUse /book to schedule a visit\\.",
            reply_markup=main_menu_keyboard(is_verified=True),
        )
        return

    text_lines = ["📋 *My Appointments*\n"]
    buttons = []

    for a in appts[:10]:
        a_id = a.get("id")
        h_name = escape_markdown(a.get("hospital_name") or "Central Branch")
        d_name = escape_markdown(a.get("doctor_name") or "Specialist Doctor")
        d_val = escape_markdown(a.get("date"))
        s_val = escape_markdown(a.get("slot"))
        st_val = escape_markdown(a.get("status", "booked").capitalize())
        reason_esc = escape_markdown(a.get("reason", "Consultation"))

        text_lines.append(
            f"• *{d_val} at {s_val}* \\({st_val}\\)\n"
            f"  👨‍⚕️ {d_name} | 🏥 {h_name}\n"
            f"  📝 Reason: {reason_esc}\n"
            f"  🆔 `{a_id}`\n"
        )

        if a.get("status") in ("booked", "accepted"):
            buttons.append([{"text": f"❌ Cancel {d_val} ({s_val})", "callback_data": f"appt:cancel:{a_id}"}])

    buttons.append([{"text": "📅 Book New Appointment", "callback_data": "nav:book"}])
    buttons.append([{"text": "🔙 Main Menu", "callback_data": "nav:main"}])

    await adapter.send_message(
        chat_id=chat_id,
        text="\n".join(text_lines),
        reply_markup=build_inline_keyboard(buttons),
    )


async def handle_appointment_cancel_callback(
    adapter: TelegramAdapter,
    chat_id: int,
    patient: Optional[Dict[str, Any]],
    appointment_id: str,
    callback_query_id: str,
) -> None:
    """Process cancellation click for an appointment."""
    if not patient:
        await adapter.answer_callback_query(callback_query_id, text="Unauthorized", show_alert=True)
        return

    patient_id = str(patient["_id"])
    try:
        res = await cancel_patient_appointment(appointment_id=appointment_id, patient_id=patient_id)
        await adapter.answer_callback_query(callback_query_id, text="Appointment Cancelled")
        await adapter.send_message(
            chat_id=chat_id,
            text=f"✅ *Appointment Cancelled*\n\nAppointment `{escape_markdown(appointment_id)}` was cancelled successfully\\. The slot is now available for other patients\\.",
            reply_markup=main_menu_keyboard(is_verified=True),
        )
    except BookingError as exc:
        await adapter.answer_callback_query(callback_query_id, text=str(exc), show_alert=True)

