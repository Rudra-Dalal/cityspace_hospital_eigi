"""Doctor routes — clinic info (open) + schedule/stats (doctor-only)."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.controllers import doctor_controller
from app.core.security import get_current_user, require_role
from app.schemas.appointment_schema import (
    DoctorInfoResponse,
    DoctorStatsResponse,
    ScheduleItem,
)

router = APIRouter(prefix="/doctor", tags=["Doctor"])

_require_doctor = Depends(require_role("doctor", "hospital_manager", "super_admin"))


@router.get("/info", response_model=DoctorInfoResponse)
async def doctor_info():
    """Public clinic and doctor details (from config, not a MongoDB collection)."""
    return doctor_controller.get_doctor_info()


@router.get("/schedule", response_model=List[ScheduleItem])
async def doctor_schedule(
    date: str = Query(None, description="ISO date YYYY-MM-DD — omit for all upcoming"),
    current_user: Dict[str, Any] = _require_doctor,
):
    """Full schedule — doctor/manager/admin only. Omit date for all upcoming."""
    return await doctor_controller.get_schedule(date, current_user)


@router.get("/stats", response_model=DoctorStatsResponse)
async def doctor_stats(current_user: Dict[str, Any] = _require_doctor):
    """Clinic statistics — scoped to doctor's hospital."""
    return await doctor_controller.get_stats(current_user)
