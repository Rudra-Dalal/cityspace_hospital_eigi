"""Generate real PDF bytes for a prescription."""

from typing import Any, Dict, Optional
from fpdf import FPDF
from app.core.config import get_settings


def _hospital_lines(hospital: Optional[Dict[str, Any]]) -> tuple[str, list[str]]:
    settings = get_settings()
    if not hospital:
        return settings.clinic_name, [settings.clinic_location]
    location = ", ".join(part for part in (hospital.get("address"), hospital.get("city"), hospital.get("state")) if part)
    contact = " | ".join(part for part in (hospital.get("contact_phone"), hospital.get("contact_email")) if part)
    return hospital.get("name") or settings.clinic_name, [line for line in (location, contact) if line]


def generate_prescription_pdf(prescription: Dict[str, Any], appointment: Dict[str, Any], doctor: Dict[str, Any], patient: Dict[str, Any], hospital: Optional[Dict[str, Any]] = None) -> bytes:
    hospital_name, header_lines = _hospital_lines(hospital)
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(text=hospital_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for line in header_lines:
        pdf.cell(text=line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 15); pdf.cell(text="PRESCRIPTION", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    doctor_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()
    patient_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip()
    for line in (f"Patient: {patient_name}", f"Doctor: {doctor_name}", f"Hospital: {hospital_name}", f"Appointment: {appointment.get('date', '')} {appointment.get('slot', '')}", f"Prescription date: {prescription['created_at'].date().isoformat()}"):
        pdf.cell(text=line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4); pdf.set_font("Helvetica", "B", 11); pdf.cell(text="DIAGNOSIS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10); pdf.multi_cell(w=0, text=prescription["diagnosis"])
    pdf.ln(3); pdf.set_font("Helvetica", "B", 11); pdf.cell(text="MEDICINES", new_x="LMARGIN", new_y="NEXT")
    for i, medicine in enumerate(prescription["medicines"], 1):
        pdf.set_font("Helvetica", "B", 10); pdf.cell(text=f"{i}. {medicine['name']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(w=0, text=f"Dosage: {medicine['dosage']}\nFrequency: {medicine['frequency']}\nDuration: {medicine['duration']}\nInstructions: {medicine.get('instructions') or '-'}")
        pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11); pdf.cell(text="GENERAL INSTRUCTIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10); pdf.multi_cell(w=0, text=prescription.get("general_instructions") or "-")
    pdf.ln(15); pdf.cell(text="Doctor signature: ______________________________", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
