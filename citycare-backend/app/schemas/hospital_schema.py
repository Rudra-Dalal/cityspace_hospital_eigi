"""Pydantic schemas for hospitals."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class HospitalCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    address: str = Field(..., min_length=5)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    contact_phone: str
    contact_email: EmailStr
    facilities: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    working_hours: Optional[str] = "09:00 - 20:00"
    emergency_contact: Optional[str] = None
    status: Optional[str] = "active"


class HospitalUpdate(BaseModel):
    """Admin update schema — super admin may change all fields including status."""
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    facilities: Optional[List[str]] = None
    services: Optional[List[str]] = None
    working_hours: Optional[str] = None
    emergency_contact: Optional[str] = None
    status: Optional[str] = None  # "active" | "inactive"


class HospitalManagerUpdate(BaseModel):
    """Manager update schema — hospital managers can update operational details but NOT status."""
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    facilities: Optional[List[str]] = None
    services: Optional[List[str]] = None
    working_hours: Optional[str] = None
    emergency_contact: Optional[str] = None


class HospitalOut(BaseModel):
    id: str
    name: str
    address: str
    city: str
    state: str
    contact_phone: str
    contact_email: str
    facilities: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    working_hours: Optional[str] = "09:00 - 20:00"
    emergency_contact: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
