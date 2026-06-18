"""
Centralized application configuration using Pydantic Settings.
Loads environment variables from Backend/.env first, falls back to project root .env.
"""

import os
import logging
from typing import Dict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Try Backend/.env first, then fall back to project root .env
_backend_env = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".env",
)
_root_env = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)

if os.path.exists(_backend_env):
    load_dotenv(dotenv_path=_backend_env)
elif os.path.exists(_root_env):
    load_dotenv(dotenv_path=_root_env)

logger = logging.getLogger(__name__)


# Per-category importance weights for scoring (PRD §10)
DEFAULT_CATEGORY_WEIGHTS: Dict[str, float] = {
    "World": 1.3,
    "India": 1.2,
    "Business": 1.1,
    "Tech": 1.0,
    "Sports": 0.9,
    "Entertainment": 0.8,
    "Lifestyle": 0.7,
}


class Settings(BaseSettings):
    """Application settings — automatically reads from environment variables."""

    # Core credentials
    database_url: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"

    # Embedding model
    embedding_model: str = "models/gemini-embedding-2"
    vector_dimensions: int = 3072
    embedding_batch_size: int = 20

    # RAG parameters
    rag_top_k: int = 6
    rag_time_window_days: int = 7

    # Clustering thresholds
    cluster_similarity_threshold: float = 0.82
    cluster_ambiguous_threshold: float = 0.70

    # Scoring
    category_weights: Dict[str, float] = DEFAULT_CATEGORY_WEIGHTS

    # Ingestion pipeline
    summary_critique_max_retries: int = 2
    cluster_verify_max_retries: int = 2

    # Connection pooling
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Cluster merging
    cluster_merge_similarity_threshold: float = 0.88
    cluster_merge_interval_hours: int = 4

    # Background tasks toggles
    enable_background_ingestion: bool = False
    background_ingestion_interval_hours: float = 12.0

    class Config:
        extra = "ignore"


settings = Settings()
