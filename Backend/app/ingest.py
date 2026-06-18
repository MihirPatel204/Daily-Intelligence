"""
Ingestion Pipeline — LangGraph-powered news processing.

Delegates to the LangGraph StateGraph defined in app/ingestion/graph.py.
The graph handles: fetch RSS → embed → cluster → score → summarize → critique.

This module provides the `run_pipeline()` entry point called by the
background scheduler and the /api/ingest endpoint.
"""

import logging
import datetime
from typing import Dict, Any

from app.ingestion.graph import get_ingestion_graph
from app.ingestion.state import IngestionState

logger = logging.getLogger(__name__)


def run_pipeline() -> Dict[str, Any]:
    """
    Run the full ingestion pipeline via LangGraph.

    Returns a summary dict with counts and status.
    """
    logger.info("Executing LangGraph news ingestion pipeline...")

    graph = get_ingestion_graph()

    # Initialize state
    initial_state: IngestionState = {
        "new_articles": [],
        "articles_to_embed": [],
        "articles_to_cluster": [],
        "active_clusters": {},
        "current_article": None,
        "candidate_cluster_id": None,
        "best_similarity": 0.0,
        "verify_retry_count": 0,
        "current_cluster_id": None,
        "draft_headline": "",
        "draft_summary": "",
        "critique_feedback": "",
        "critique_retry_count": 0,
        "fetch_count": 0,
        "embed_count": 0,
        "cluster_count": 0,
        "synthesize_count": 0,
        "errors": [],
    }

    try:
        # Run the graph synchronously
        final_state = graph.invoke(initial_state)

        result = {
            "status": "success",
            "new_articles_fetched": final_state.get("fetch_count", 0),
            "articles_embedded": final_state.get("embed_count", 0),
            "new_clusters_created": final_state.get("cluster_count", 0),
            "clusters_synthesized": final_state.get("synthesize_count", 0),
            "errors": final_state.get("errors", []),
            "timestamp": datetime.datetime.now().isoformat(),
        }

        logger.info(f"Pipeline completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat(),
        }




if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_pipeline()
