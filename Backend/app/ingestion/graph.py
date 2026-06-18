"""
Ingestion Graph — LangGraph StateGraph for the news processing pipeline.

Models the ingestion pipeline per PRD §8 as:
  fetch → embed → cluster_match → score → summarize ⇄ critique → END

The summarize ↔ critique loop is a conditional edge: if critique finds
issues, it routes back to summarize with feedback. Bounded by
settings.summary_critique_max_retries.
"""

import logging
from langgraph.graph import StateGraph, END

from app.ingestion.state import IngestionState
from app.ingestion.nodes import (
    fetch_node,
    embed_node,
    cluster_match_node,
    score_node,
    summarize_node,
    critique_node,
)

logger = logging.getLogger(__name__)

_compiled_ingestion_graph = None


def _should_retry_summary(state: IngestionState) -> str:
    """
    Conditional edge after critique_node:
    If critique_feedback is non-empty and we haven't exceeded retries,
    loop back to summarize. Otherwise proceed to END.
    """
    feedback = state.get("critique_feedback", "")
    if feedback:
        logger.info("Critique returned feedback — looping back to summarize.")
        return "retry_summarize"
    return "done"


def build_ingestion_graph():
    """Construct and compile the ingestion pipeline StateGraph."""
    workflow = StateGraph(IngestionState)

    # Register nodes
    workflow.add_node("fetch", fetch_node)
    workflow.add_node("embed", embed_node)
    workflow.add_node("cluster_match", cluster_match_node)
    workflow.add_node("score", score_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("critique", critique_node)

    # Linear edges: fetch → embed → cluster_match → score → summarize
    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "embed")
    workflow.add_edge("embed", "cluster_match")
    workflow.add_edge("cluster_match", "score")
    workflow.add_edge("score", "summarize")

    # summarize → critique
    workflow.add_edge("summarize", "critique")

    # Conditional edge: critique → summarize (retry) or END
    workflow.add_conditional_edges(
        "critique",
        _should_retry_summary,
        {
            "retry_summarize": "summarize",
            "done": END,
        },
    )

    compiled = workflow.compile()
    logger.info("LangGraph ingestion pipeline compiled successfully.")
    return compiled


def get_ingestion_graph():
    """Return the singleton compiled ingestion graph."""
    global _compiled_ingestion_graph
    if _compiled_ingestion_graph is None:
        _compiled_ingestion_graph = build_ingestion_graph()
    return _compiled_ingestion_graph
