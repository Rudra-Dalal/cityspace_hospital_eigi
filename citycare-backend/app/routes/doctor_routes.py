"""Doctor routes — clinic info (open) + schedule/stats (doctor-only)."""

from typing import List

from fastapi import APIRouter, Depends, Query

from app.controllers import doctor_controller
from app.core.security import require_doctor
from app.schemas.appointment_schema import (
    DoctorInfoResponse,
    DoctorStatsResponse,
    ScheduleItem,
)

router = APIRouter(prefix="/doctor", tags=["Doctor"])


@router.get("/info", response_model=DoctorInfoResponse)
async def doctor_info():
    """Public clinic and doctor details (from config, not a MongoDB collection)."""
    return doctor_controller.get_doctor_info()


@router.get("/schedule", response_model=List[ScheduleItem])
async def doctor_schedule(
    date: str = Query(..., description="ISO date YYYY-MM-DD"),
    _doctor=Depends(require_doctor),
):
    """Full schedule for a date — doctor only. Patients receive 403."""
    return await doctor_controller.get_schedule(date)


@router.get("/stats", response_model=DoctorStatsResponse)
async def doctor_stats(_doctor=Depends(require_doctor)):
    """Clinic statistics — doctor only."""
    return await doctor_controller.get_stats()
