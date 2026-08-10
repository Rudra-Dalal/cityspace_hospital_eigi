from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from app.controllers import prescription_controller
from app.core.security import get_current_user
from app.schemas.prescription_schema import PrescriptionCreate, PrescriptionOut

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])

@router.post("", response_model=PrescriptionOut, status_code=201)
async def create_prescription(payload: PrescriptionCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    return await prescription_controller.create(payload, current_user)

@router.get("/my", response_model=List[PrescriptionOut])
async def my_prescriptions(current_user: Dict[str, Any] = Depends(get_current_user)):
    return await prescription_controller.mine(current_user)

@router.get("/{prescription_id}", response_model=PrescriptionOut)
async def get_prescription(prescription_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    return await prescription_controller.get_one(prescription_id, current_user)
