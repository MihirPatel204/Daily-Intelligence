"""Pydantic schemas for Cluster and Article responses."""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ArticleResponse(BaseModel):
    """Serialized article within a cluster."""

    id: int
    source_id: int
    source_name: Optional[str] = None
    url: str
    title: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    image_url: Optional[str] = None
    cluster_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ClusterResponse(BaseModel):
    """Serialized cluster with nested articles."""

    id: int
    headline: str
    synthesized_summary: Optional[str] = None
    category: str
    score: float
    size_tier: str
    outlet_count: int
    first_seen_at: datetime
    last_updated_at: datetime
    articles: List[ArticleResponse] = []

    class Config:
        from_attributes = True
