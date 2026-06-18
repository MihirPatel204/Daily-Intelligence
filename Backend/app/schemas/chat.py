"""Pydantic schemas for Chat request/response models."""

from pydantic import BaseModel
from typing import List, Optional


class Citation(BaseModel):
    """A source citation grounding a claim in a chat response."""

    title: str
    url: str
    source_name: str


class ChatRequest(BaseModel):
    """Incoming chat message from the frontend."""

    message: str
    session_id: Optional[str] = "default-session"


class ChatResponse(BaseModel):
    """Non-streaming chat response (fallback)."""

    answer: str
    citations: List[Citation] = []
