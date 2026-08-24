"""Public patient-safe discovery routes for hospitals and doctors."""

from typing import List, Optional

from fastapi import APIRouter, Query

from app.controllers import patient_controller
from app.schemas.hospital_schema import HospitalOut
from app.schemas.user_schema import DoctorAvailabilityOut, DoctorPublicOut

router = APIRouter(prefix="/patient", tags=["Patient Discovery"])


@router.get("/hospitals", response_model=List[HospitalOut])
async def list_active_hospitals():
    """List all active hospitals with facilities and services. Public endpoint."""
    return await patient_controller.list_active_hospitals()


@router.get("/hospitals/{hospital_id}", response_model=HospitalOut)
async def get_hospital_details(hospital_id: str):
    """Get details of a specific active hospital. Public endpoint."""
    return await patient_controller.get_hospital_details(hospital_id)


@router.get("/doctors", response_model=List[DoctorPublicOut])
async def list_active_doctors(
    specialization: Optional[str] = Query(None, description="Filter by doctor specialization"),
    hospital_id: Optional[str] = Query(None, description="Filter by hospital ID"),
):
    """List all active doctors with optional specialization or hospital filtering. Public endpoint."""
    return await patient_controller.list_active_doctors(
        specialization=specialization,
        hospital_id=hospital_id,
    )


@router.get("/doctors/{doctor_id}", response_model=DoctorPublicOut)
async def get_doctor_details(doctor_id: str):
    """Get public profile of a specific active doctor. Public endpoint."""
    return await patient_controller.get_doctor_details(doctor_id)


@router.get("/doctors/{doctor_id}/availability", response_model=DoctorAvailabilityOut)
async def get_doctor_availability(
    doctor_id: str,
    date: str = Query(..., description="ISO date YYYY-MM-DD within booking window"),
):
    """Get doctor-specific availability and remaining appointment slots for a given date. Public endpoint."""
    return await patient_controller.get_doctor_availability(doctor_id, date)
