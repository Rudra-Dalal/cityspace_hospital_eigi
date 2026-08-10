"""Generate real PDF bytes for a prescription."""

from io import BytesIO
from typing import Any, Dict
from fpdf import FPDF
from app.core.config import get_settings


def generate_prescription_pdf(prescription: Dict[str, Any], appointment: Dict[str, Any], doctor: Dict[str, Any], patient: Dict[str, Any]) -> bytes:
    settings = get_settings()
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(text=settings.clinic_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(text=settings.clinic_location, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 15); pdf.cell(text="PRESCRIPTION", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    doctor_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()
    patient_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip()
    for line in (f"Doctor: {doctor_name}", f"Patient: {patient_name}", f"Appointment: {appointment.get('date', '')} {appointment.get('slot', '')}", f"Prescription date: {prescription['created_at'].date().isoformat()}"):
        pdf.cell(text=line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4); pdf.set_font("Helvetica", "B", 11); pdf.cell(text="Diagnosis", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10); pdf.multi_cell(w=0, text=prescription["diagnosis"])
    pdf.ln(3); pdf.set_font("Helvetica", "B", 11); pdf.cell(text="MEDICINES", new_x="LMARGIN", new_y="NEXT")
    for i, medicine in enumerate(prescription["medicines"], 1):
        pdf.set_font("Helvetica", "B", 10); pdf.cell(text=f"{i}. {medicine['name']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(w=0, text=f"Dosage: {medicine['dosage']} | Frequency: {medicine['frequency']} | Duration: {medicine['duration']}\nInstructions: {medicine.get('instructions') or '-'}")
        pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11); pdf.cell(text="General instructions", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10); pdf.multi_cell(w=0, text=prescription.get("general_instructions") or "-")
    pdf.ln(15); pdf.cell(text="Doctor signature: ______________________________", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
