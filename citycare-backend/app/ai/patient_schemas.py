from pydantic import BaseModel, Field, field_validator

class PatientChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip(): raise ValueError("Message cannot be blank")
        return value.strip()

class PatientChatResponse(BaseModel):
    reply: str
    sources: list[str] = []
