from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from app.ai.patient_schemas import PatientChatRequest, PatientChatResponse
from app.ai.patient_service import run_patient_chat
from app.core.security import get_current_user

router = APIRouter(prefix="/patient-ai", tags=["Patient Prescription Assistant"])

@router.post("/chat", response_model=PatientChatResponse)
async def patient_chat(payload: PatientChatRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.get("role") not in ("customer", "patient"):
        raise HTTPException(status_code=403, detail="Only patients can use the prescription assistant.")
    try:
        reply, sources = await run_patient_chat(payload.message, current_user)
        return PatientChatResponse(reply=reply, sources=sources)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="The prescription assistant is temporarily unavailable.")
