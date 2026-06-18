"""
Clusters Router — GET endpoints for newspaper front-page data.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException

from app.db import get_db_connection, return_db_connection
from app.schemas.cluster import ClusterResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/clusters", response_model=List[ClusterResponse])
def get_clusters():
    """Retrieve all active clusters from the last 48 hours, sorted by score."""
    conn = get_db_connection()
    clusters_dict: dict = {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, headline, synthesized_summary, category, score,
                       size_tier, outlet_count, first_seen_at, last_updated_at
                FROM clusters
                WHERE last_updated_at > NOW() - INTERVAL '48 hours'
                ORDER BY score DESC;
            """)
            clusters_raw = cur.fetchall()

            if not clusters_raw:
                return []

            cluster_ids = [c[0] for c in clusters_raw]

            for c in clusters_raw:
                clusters_dict[c[0]] = {
                    "id": c[0],
                    "headline": c[1],
                    "synthesized_summary": c[2],
                    "category": c[3],
                    "score": c[4],
                    "size_tier": c[5],
                    "outlet_count": c[6],
                    "first_seen_at": c[7],
                    "last_updated_at": c[8],
                    "articles": [],
                }

            cur.execute("""
                SELECT a.id, a.source_id, s.name AS source_name, a.url, a.title,
                       a.summary, a.published_at, a.image_url, a.cluster_id, a.created_at
                FROM articles a
                JOIN sources s ON a.source_id = s.id
                WHERE a.cluster_id IN %s
                ORDER BY a.published_at DESC;
            """, (tuple(cluster_ids),))

            for art in cur.fetchall():
                cid = art[8]
                if cid in clusters_dict:
                    clusters_dict[cid]["articles"].append({
                        "id": art[0],
                        "source_id": art[1],
                        "source_name": art[2],
                        "url": art[3],
                        "title": art[4],
                        "summary": art[5],
                        "published_at": art[6],
                        "image_url": art[7],
                        "cluster_id": art[8],
                        "created_at": art[9],
                    })

        return list(clusters_dict.values())
    except Exception as e:
        logger.error(f"Error fetching clusters: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred.")
    finally:
        return_db_connection(conn)


@router.get("/api/clusters/{cluster_id}", response_model=ClusterResponse)
def get_cluster(cluster_id: int):
    """Retrieve a single cluster and its articles."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, headline, synthesized_summary, category, score,
                       size_tier, outlet_count, first_seen_at, last_updated_at
                FROM clusters
                WHERE id = %s;
            """, (cluster_id,))
            c = cur.fetchone()
            if not c:
                raise HTTPException(status_code=404, detail="Cluster not found.")

            cluster_data = {
                "id": c[0],
                "headline": c[1],
                "synthesized_summary": c[2],
                "category": c[3],
                "score": c[4],
                "size_tier": c[5],
                "outlet_count": c[6],
                "first_seen_at": c[7],
                "last_updated_at": c[8],
                "articles": [],
            }

            cur.execute("""
                SELECT a.id, a.source_id, s.name AS source_name, a.url, a.title,
                       a.summary, a.published_at, a.image_url, a.cluster_id, a.created_at
                FROM articles a
                JOIN sources s ON a.source_id = s.id
                WHERE a.cluster_id = %s
                ORDER BY a.published_at DESC;
            """, (cluster_id,))

            for art in cur.fetchall():
                cluster_data["articles"].append({
                    "id": art[0],
                    "source_id": art[1],
                    "source_name": art[2],
                    "url": art[3],
                    "title": art[4],
                    "summary": art[5],
                    "published_at": art[6],
                    "image_url": art[7],
                    "cluster_id": art[8],
                    "created_at": art[9],
                })

            return cluster_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cluster {cluster_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred.")
    finally:
        return_db_connection(conn)
