"""Pydantic schemas for auth / users."""

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user_model import UserRole


class SignupRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    mobile: str = Field(..., description="Indian mobile with +91")
    password: str = Field(..., min_length=8, max_length=128)
    # Even if a client sends role, signup ignores it and always creates a customer
    role: Optional[UserRole] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("mobile")
    @classmethod
    def validate_indian_mobile(cls, v: str) -> str:
        v = v.strip()
        # Accept +91 followed by 10 digits starting 6–9
        if not re.fullmatch(r"\+91[6-9]\d{9}", v):
            raise ValueError("mobile must match +91 followed by a 10-digit Indian number")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    mobile: str
    role: UserRole
    hospital_id: Optional[str] = None
    is_active: bool = True
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    available_days: Optional[List[str]] = None
    working_hours: Optional[str] = None
    slot_duration_minutes: Optional[int] = None
    valid_slots: Optional[List[str]] = None
    created_at: Optional[datetime] = None


class DoctorPublicOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    mobile: str
    role: str = "doctor"
    qualification: str = "MBBS"
    specialization: str = "General Physician"
    hospital_id: Optional[str] = None
    hospital_name: Optional[str] = None
    is_active: bool = True
    available_days: List[str] = Field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
    working_hours: Optional[str] = "10:00 - 20:00"
    slot_duration_minutes: int = 30
    valid_slots: List[str] = Field(default_factory=list)


class DoctorAvailabilityOut(BaseModel):
    doctor_id: str
    hospital_id: Optional[str] = None
    date: str
    day_of_week: str
    is_available: bool
    available_slots: List[str]
    all_slots: List[str]
    message: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Admin management schemas
# ---------------------------------------------------------------------------

class CreateManagerRequest(BaseModel):
    """Super admin creates a hospital manager."""
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    mobile: str = Field(..., description="Indian mobile with +91")
    password: str = Field(..., min_length=8, max_length=128)
    hospital_id: str = Field(..., description="ObjectId of the hospital to assign")

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: str) -> str:
        return v.strip()

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\+91[6-9]\d{9}", v):
            raise ValueError("mobile must match +91 followed by a 10-digit Indian number")
        return v


class CreateDoctorRequest(BaseModel):
    """Super admin or hospital manager creates a doctor."""
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    mobile: str = Field(..., description="Indian mobile with +91")
    password: str = Field(..., min_length=8, max_length=128)
    hospital_id: str = Field(..., description="ObjectId of the hospital to assign")
    qualification: Optional[str] = "MBBS"
    specialization: Optional[str] = "General Physician"
    available_days: Optional[List[str]] = None
    working_hours: Optional[str] = None
    valid_slots: Optional[List[str]] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: str) -> str:
        return v.strip()

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\+91[6-9]\d{9}", v):
            raise ValueError("mobile must match +91 followed by a 10-digit Indian number")
        return v
