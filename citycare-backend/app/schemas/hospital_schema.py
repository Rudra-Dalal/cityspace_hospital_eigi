"""Pydantic schemas for hospitals."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class HospitalCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    address: str = Field(..., min_length=5)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    contact_phone: str
    contact_email: EmailStr


class HospitalUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    status: Optional[str] = None  # "active" | "inactive"


class HospitalOut(BaseModel):
    id: str
    name: str
    address: str
    city: str
    state: str
    contact_phone: str
    contact_email: str
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
