from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel


class VoiceSessionOut(BaseModel):
    id: uuid.UUID
    transcript: Optional[str]
    assistant_reply: Optional[str]
    duration_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    mime_type: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_conversations: int
    total_messages: int
    total_voice_sessions: int
    total_documents: int
    tokens_prompt_30d: int
    tokens_completion_30d: int
