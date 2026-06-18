"""
Backward-compatibility re-exports.

All schemas now live in app.schemas.* — this file ensures that any
existing imports from ``app.models`` still work.
"""

from app.schemas.cluster import ClusterResponse, ArticleResponse  # noqa: F401
from app.schemas.chat import ChatRequest, ChatResponse, Citation  # noqa: F401

__all__ = [
    "ClusterResponse",
    "ArticleResponse",
    "ChatRequest",
    "ChatResponse",
    "Citation",
]
