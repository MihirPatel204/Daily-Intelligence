"""
RAG Graph — LangGraph StateGraph definition.

Compiles the retrieve → grade → generate workflow with a MemorySaver
checkpointer so that conversation messages persist across invocations
for the same thread_id (session).
"""

import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.rag.state import RAGState
from app.rag.nodes import retrieve_node, grade_node, generate_node

logger = logging.getLogger(__name__)

# Shared in-memory checkpointer for multi-turn conversation memory.
# In production this could be swapped for a Postgres-backed checkpointer.
_checkpointer = MemorySaver()
_compiled_graph = None


def build_rag_graph():
    """Construct and compile the RAG workflow graph."""
    workflow = StateGraph(RAGState)

    # Register nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("generate", generate_node)

    # Linear pipeline: retrieve → grade → generate → END
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade")
    workflow.add_edge("grade", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile(checkpointer=_checkpointer)


def get_rag_graph():
    """Return the singleton compiled RAG graph."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_rag_graph()
        logger.info("LangGraph RAG workflow compiled successfully.")
    return _compiled_graph
