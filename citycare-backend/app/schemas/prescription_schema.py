"""Validated API schemas for prescriptions."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class MedicineInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    duration: str = Field(..., min_length=1, max_length=100)
    instructions: str = Field("", max_length=500)

    @field_validator("name", "dosage", "frequency", "duration")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field cannot be blank")
        return value.strip()


class PrescriptionCreate(BaseModel):
    appointment_id: str = Field(..., min_length=1)
    diagnosis: str = Field(..., min_length=1, max_length=2000)
    medicines: List[MedicineInput] = Field(..., min_length=1, max_length=30)
    general_instructions: str = Field("", max_length=4000)

    @field_validator("diagnosis")
    @classmethod
    def diagnosis_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Diagnosis cannot be blank")
        return value.strip()


class MedicineOut(MedicineInput):
    pass


class PrescriptionHospital(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    contact_phone: Optional[str] = None


class PrescriptionOut(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    hospital_id: Optional[str] = None
    appointment_id: str
    diagnosis: str
    medicines: List[MedicineOut]
    general_instructions: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pdf_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None
    hospital: Optional[PrescriptionHospital] = None
