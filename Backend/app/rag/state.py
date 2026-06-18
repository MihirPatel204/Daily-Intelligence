"""
RAG State — typed state schema for the LangGraph RAG workflow.

The `messages` field uses LangGraph's `add_messages` annotation so that
new messages are appended (not overwritten) across graph invocations,
enabling multi-turn conversation memory via the checkpointer.
"""

from typing import TypedDict, List, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class RAGState(TypedDict):
    """State schema flowing through the RAG graph."""

    # Conversation history — accumulated across invocations via checkpointer
    messages: Annotated[list[BaseMessage], add_messages]

    # Per-invocation fields (overwritten each call)
    question: str
    documents: list[dict]
    cluster_id: Optional[int]
    generation: str
    citations: list[dict]
