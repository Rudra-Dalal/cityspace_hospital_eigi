"""Super Admin API routes — hospital & user management."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.controllers import admin_controller
from app.core.security import get_current_user, require_role
from app.schemas.hospital_schema import HospitalCreate, HospitalOut, HospitalUpdate
from app.schemas.user_schema import CreateDoctorRequest, CreateManagerRequest, UserOut

router = APIRouter(prefix="/admin", tags=["Super Admin"])

bearer_scheme = HTTPBearer(auto_error=False)

# Dependency shortcut — only super_admin can access these routes
_require_super_admin = Depends(require_role("super_admin"))


# ---------------------------------------------------------------------------
# Hospital endpoints
# ---------------------------------------------------------------------------

@router.post("/hospitals", response_model=HospitalOut, status_code=201)
async def create_hospital(
    payload: HospitalCreate,
    current_user=_require_super_admin,
):
    return await admin_controller.create_hospital(payload, created_by=current_user["id"])


@router.get("/hospitals", response_model=List[HospitalOut])
async def list_hospitals(
    status: Optional[str] = Query(None, description="Filter by status: active | inactive"),
    current_user=_require_super_admin,
):
    return await admin_controller.list_hospitals(status=status)


@router.patch("/hospitals/{hospital_id}", response_model=HospitalOut)
async def update_hospital(
    hospital_id: str,
    payload: HospitalUpdate,
    current_user=_require_super_admin,
):
    return await admin_controller.update_hospital(hospital_id, payload)


# ---------------------------------------------------------------------------
# User management endpoints
# ---------------------------------------------------------------------------

@router.post("/users/manager", response_model=UserOut, status_code=201)
async def create_manager(
    payload: CreateManagerRequest,
    current_user=_require_super_admin,
):
    return await admin_controller.create_manager(payload, created_by=current_user["id"])


@router.post("/users/doctor", response_model=UserOut, status_code=201)
async def create_doctor(
    payload: CreateDoctorRequest,
    current_user=_require_super_admin,
):
    return await admin_controller.create_doctor(payload, created_by=current_user["id"])


@router.get("/users", response_model=List[UserOut])
async def list_users(
    role: Optional[str] = Query(None),
    hospital_id: Optional[str] = Query(None),
    current_user=_require_super_admin,
):
    return await admin_controller.list_users(role=role, hospital_id=hospital_id)


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: str,
    current_user=_require_super_admin,
):
    return await admin_controller.deactivate_user(user_id)
