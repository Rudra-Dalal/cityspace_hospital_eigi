"""Pydantic schemas for the AI chat endpoint."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v.strip()

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Must be a valid UUID-like hex string (alphanumeric + hyphens)
        import re
        if not re.match(r"^[a-zA-Z0-9\-]{8,64}$", v):
            raise ValueError("conversation_id is invalid")
        return v


class AIChatResponse(BaseModel):
    reply: str
    conversation_id: str
    tool_calls_made: list[str] = Field(default_factory=list)
