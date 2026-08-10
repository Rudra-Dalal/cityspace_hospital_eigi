"""Appointment routes."""

from typing import List
from fastapi import APIRouter, Depends, Query
from app.controllers import appointment_controller
from app.core.security import get_current_user
from app.schemas.appointment_schema import (
    AppointmentCreate,
    AppointmentOut,
    AcceptResponse,
    CancelResponse,
    FreeSlotsResponse,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("/free-slots", response_model=FreeSlotsResponse)
async def free_slots(
    date: str = Query(..., description="ISO date YYYY-MM-DD"),
    doctor_id: str = Query(None),
    hospital_id: str = Query(None),
):
    """Return still-free slots for a date (menu minus booked). Open endpoint."""
    return await appointment_controller.get_free_slots(date, doctor_id=doctor_id, hospital_id=hospital_id)


@router.post("", response_model=AppointmentOut, status_code=201)
async def book_appointment(
    payload: AppointmentCreate,
    current_user=Depends(get_current_user),
):
    """Book an appointment. Patient identity comes from JWT only."""
    return await appointment_controller.book_appointment(payload, current_user)


@router.get("/my", response_model=List[AppointmentOut])
async def my_appointments(current_user=Depends(get_current_user)):
    """List the authenticated patient's appointments, newest first."""
    return await appointment_controller.list_my_appointments(current_user)


@router.patch("/{appointment_id}/cancel", response_model=CancelResponse)
async def cancel_appointment(
    appointment_id: str,
    current_user=Depends(get_current_user),
):
    """Cancel an appointment (owner or doctor). Frees the slot via status change."""
    return await appointment_controller.cancel_my_appointment(
        appointment_id, current_user
    )


@router.patch("/{appointment_id}/accept", response_model=AcceptResponse)
async def accept_appointment(appointment_id: str, current_user=Depends(get_current_user)):
    """Accept a booked appointment. Only its assigned doctor may do this."""
    return await appointment_controller.accept_appointment(appointment_id, current_user)
