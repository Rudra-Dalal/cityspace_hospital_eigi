"""AI chat route — doctor-only endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict

from app.ai.schemas import AIChatRequest, AIChatResponse
from app.ai.service import run_chat
from app.ai.tools import TOOL_LABELS
from app.core.security import require_doctor_dep
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["Doctor AI Assistant"])


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    payload: AIChatRequest,
    current_user: Dict[str, Any] = Depends(require_doctor_dep),
) -> AIChatResponse:
    """
    Doctor-only AI chat endpoint.

    - Authentication: JWT bearer token (existing system).
    - Authorization: doctor role required (require_doctor_dep).
    - The doctor's identity is ALWAYS taken from the JWT, never from the request body.
    - Gemini is called only from this backend; the API key never reaches the browser.
    - All tools are read-only; no data mutations are possible.
    """
    try:
        reply, conv_id, tools_called = await run_chat(
            message=payload.message,
            conversation_id=payload.conversation_id,
            current_user=current_user,
        )
    except ValueError as exc:
        if "rate_limited" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You've reached the AI request limit. Please try again shortly.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except RuntimeError as exc:
        err_msg = str(exc)
        logger.error("AI_ERROR user=%s error=%s", current_user.get("email"), err_msg)
        if "GEMINI_API_KEY" in err_msg or "disabled" in err_msg or "not installed" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The AI assistant is temporarily unavailable. Please try again later.",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI assistant is temporarily unavailable. Please try again later.",
        )
    except TimeoutError:
        logger.error("AI_TIMEOUT user=%s", current_user.get("email"))
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI request took too long. Please try again.",
        )
    except Exception as exc:
        logger.exception("AI_ERROR unhandled user=%s error=%s", current_user.get("email"), exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Something went wrong while contacting the AI assistant.",
        )

    # Convert tool names to human-readable labels
    tool_labels = [TOOL_LABELS.get(t, t) for t in tools_called]

    return AIChatResponse(
        reply=reply,
        conversation_id=conv_id,
        tool_calls_made=tool_labels,
    )
