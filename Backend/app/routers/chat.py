"""
Chat Router — streaming SSE endpoints for story-scoped and global RAG chat.

Both endpoints return ``StreamingResponse`` with ``text/event-stream``
content type, delivering tokens in real time as the LangGraph RAG agent
processes the query.
"""

import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.rag_service import stream_rag_response

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/chat")
async def global_chat(request: ChatRequest):
    """Corpus-wide news chat with streaming SSE response."""
    return StreamingResponse(
        stream_rag_response(
            question=request.message,
            session_id=request.session_id or "global-default",
            cluster_id=None,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/clusters/{cluster_id}/chat")
async def story_chat(cluster_id: int, request: ChatRequest):
    """Story-scoped chat with streaming SSE response."""
    return StreamingResponse(
        stream_rag_response(
            question=request.message,
            session_id=request.session_id or f"story-{cluster_id}",
            cluster_id=cluster_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
