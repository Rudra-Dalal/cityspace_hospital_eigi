"""Pydantic schemas for appointments and doctor views."""

import re
from datetime import date as date_cls
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.config import ALLOWED_SYMPTOMS, VALID_SLOTS
from app.models.appointment_model import AppointmentStatus


class AppointmentCreate(BaseModel):
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    slot: str
    reason: str = Field(..., min_length=1)
    temperature: Optional[float] = None
    symptoms: List[str] = Field(default_factory=list)
    # Multi-tenant fields — optional for backward compat (controller resolves defaults)
    hospital_id: Optional[str] = None
    doctor_id: Optional[str] = None

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            date_cls.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("date must be a valid ISO date YYYY-MM-DD") from exc
        return v

    @field_validator("slot")
    @classmethod
    def validate_slot(cls, v: str) -> str:
        if v not in VALID_SLOTS:
            raise ValueError(f"slot must be one of: {', '.join(VALID_SLOTS)}")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        cleaned = v.strip()
        # At least 10 non-whitespace characters
        if len(re.sub(r"\s+", "", cleaned)) < 10:
            raise ValueError("reason must contain at least 10 non-whitespace characters")
        return cleaned

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not 95.0 <= v <= 110.0:
            raise ValueError("temperature must be between 95 and 110 Fahrenheit")
        return v

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, v: List[str]) -> List[str]:
        invalid = [s for s in v if s not in ALLOWED_SYMPTOMS]
        if invalid:
            raise ValueError(
                f"invalid symptoms: {', '.join(invalid)}. "
                f"Allowed: {', '.join(ALLOWED_SYMPTOMS)}"
            )
        seen = set()
        unique = []
        for s in v:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique


class AppointmentOut(BaseModel):
    id: str
    patient_id: str
    hospital_id: Optional[str] = None
    doctor_id: Optional[str] = None
    date: str
    slot: str
    reason: str
    temperature: Optional[float] = None
    symptoms: List[str] = Field(default_factory=list)
    status: AppointmentStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    patient_name: Optional[str] = None


class FreeSlotsResponse(BaseModel):
    date: str
    free_slots: List[str]


class DoctorInfoResponse(BaseModel):
    name: str
    qualification: str
    clinic_name: str
    clinic_location: str
    morning_hours: str
    evening_hours: str
    slot_duration_minutes: int
    valid_slots: List[str]


class DoctorStatsResponse(BaseModel):
    total_patients: int
    today_visits: int
    upcoming_visits: int


class ScheduleItem(BaseModel):
    id: str
    slot: str
    date: str
    patient_name: str
    reason: str
    temperature: Optional[float] = None
    symptoms: List[str] = Field(default_factory=list)
    status: AppointmentStatus


class CancelResponse(BaseModel):
    id: str
    status: AppointmentStatus
    detail: str = "Appointment cancelled successfully."


class AcceptResponse(BaseModel):
    id: str
    status: AppointmentStatus
    detail: str = "Appointment accepted successfully."
