from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str
    system_prompt: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Message cannot be empty or whitespace only")
        if len(trimmed) > 4000:
            raise ValueError("Message cannot exceed 4000 characters")
        return trimmed


class ChatMetadata(BaseModel):
    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str] = None
    fallback_attempts: int = 0


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata


class MessageItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    metadata: Optional[Dict[str, Any]] = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[MessageItem]


class HealthResponse(BaseModel):
    status: str = "ok"
    keys_configured: int
    cache_enabled: bool
