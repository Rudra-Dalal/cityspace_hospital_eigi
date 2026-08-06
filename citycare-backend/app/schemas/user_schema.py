"""Pydantic schemas for auth / users."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user_model import UserRole


class SignupRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    mobile: str = Field(..., description="Indian mobile with +91")
    password: str = Field(..., min_length=8, max_length=128)
    # Even if a client sends role, signup ignores it and always creates a patient
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
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
