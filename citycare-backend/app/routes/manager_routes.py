"""Hospital Manager API routes."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.controllers import manager_controller
from app.core.security import require_role
from app.schemas.hospital_schema import HospitalOut, HospitalUpdate

router = APIRouter(prefix="/manager", tags=["Hospital Manager"])

_require_manager = Depends(require_role("hospital_manager", "super_admin"))


@router.get("/hospital", response_model=HospitalOut)
async def get_my_hospital(current_user=_require_manager):
    return await manager_controller.get_my_hospital(current_user)


@router.patch("/hospital", response_model=HospitalOut)
async def update_my_hospital(
    payload: HospitalUpdate,
    current_user=_require_manager,
):
    return await manager_controller.update_my_hospital(current_user, payload)


@router.get("/doctors")
async def list_my_doctors(current_user=_require_manager):
    return await manager_controller.get_my_doctors(current_user)


@router.get("/appointments")
async def list_my_appointments(current_user=_require_manager):
    return await manager_controller.get_my_appointments(current_user)
