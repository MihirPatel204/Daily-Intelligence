"""
Ingestion State — typed state schema for the LangGraph ingestion pipeline.

Flows through the StateGraph: fetch → parse → embed → cluster → verify →
score → summarize → critique → store.
"""

from typing import TypedDict, List, Dict, Any, Optional


class ArticleData(TypedDict, total=False):
    """Data for a single article flowing through the pipeline."""
    id: int
    source_id: int
    source_name: str
    source_category: str
    url: str
    title: str
    summary: str
    published_at: str
    image_url: Optional[str]
    embedding: Optional[List[float]]
    cluster_id: Optional[int]


class ClusterData(TypedDict, total=False):
    """Data for a cluster during processing."""
    id: int
    headline: str
    category: str
    embeddings: List[List[float]]
    titles: List[str]


class IngestionState(TypedDict, total=False):
    """State schema flowing through the ingestion pipeline graph."""

    # Pipeline-level state
    new_articles: List[ArticleData]
    articles_to_embed: List[ArticleData]
    articles_to_cluster: List[ArticleData]
    active_clusters: Dict[int, ClusterData]

    # Per-article clustering state (for verify loop)
    current_article: Optional[ArticleData]
    candidate_cluster_id: Optional[int]
    best_similarity: float
    verify_retry_count: int

    # Per-cluster synthesis state (for critique loop)
    current_cluster_id: Optional[int]
    draft_headline: str
    draft_summary: str
    critique_feedback: str
    critique_retry_count: int

    # Results
    fetch_count: int
    embed_count: int
    cluster_count: int
    synthesize_count: int
    errors: List[str]
