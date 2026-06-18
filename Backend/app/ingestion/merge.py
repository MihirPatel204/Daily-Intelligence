"""
Cluster Merging — periodic pass to merge fragmented clusters.

Addresses PRD §14 concern: fast-moving stories may fragment into multiple
clusters before merging. This module compares cluster centroids and merges
clusters that are above a similarity threshold.
"""

import logging
import datetime
from typing import Dict, Any

import numpy as np

from app.config import settings
from app.db import get_db_connection, return_db_connection
from app.services.embedding_service import get_embeddings
from app.services.llm_service import get_llm
from app.ingestion.nodes import cosine_similarity, ClusterSynthesis

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


def merge_similar_clusters() -> Dict[str, Any]:
    """
    Compare centroids of recent clusters and merge those above the
    similarity threshold. Re-synthesizes merged clusters.

    Returns a summary of the merge operation.
    """
    logger.info("Starting cluster merge pass...")
    conn = get_db_connection()
    merged_count = 0

    try:
        with conn.cursor() as cur:
            # Get all recent clusters with their article embeddings
            cur.execute("""
                SELECT c.id, c.headline, c.category
                FROM clusters c
                WHERE c.last_updated_at > NOW() - INTERVAL '48 hours'
                ORDER BY c.score DESC;
            """)
            clusters = cur.fetchall()

            if len(clusters) < 2:
                logger.info("Fewer than 2 clusters — nothing to merge.")
                return {"merged": 0}

            # Compute centroids for each cluster
            cluster_centroids: Dict[int, dict] = {}
            for cid, headline, category in clusters:
                cur.execute("""
                    SELECT embedding FROM articles
                    WHERE cluster_id = %s AND embedding IS NOT NULL;
                """, (cid,))
                embeddings = cur.fetchall()

                if not embeddings:
                    continue

                emb_arrays = []
                for (emb,) in embeddings:
                    if isinstance(emb, str):
                        emb = [float(x) for x in emb.strip('[]').split(',')]
                    emb_arrays.append(np.array(emb))

                centroid = np.mean(emb_arrays, axis=0)
                cluster_centroids[cid] = {
                    "headline": headline,
                    "category": category,
                    "centroid": centroid,
                }

            # Find merge candidates
            cluster_ids = list(cluster_centroids.keys())
            merged_into: Dict[int, int] = {}  # maps merged_cluster → target_cluster

            for i in range(len(cluster_ids)):
                cid_a = cluster_ids[i]
                if cid_a in merged_into:
                    continue

                for j in range(i + 1, len(cluster_ids)):
                    cid_b = cluster_ids[j]
                    if cid_b in merged_into:
                        continue

                    sim = cosine_similarity(
                        cluster_centroids[cid_a]["centroid"],
                        cluster_centroids[cid_b]["centroid"],
                    )

                    if sim >= settings.cluster_merge_similarity_threshold:
                        logger.info(
                            f"Merging cluster {cid_b} "
                            f"('{cluster_centroids[cid_b]['headline'][:40]}') "
                            f"into {cid_a} "
                            f"('{cluster_centroids[cid_a]['headline'][:40]}') "
                            f"sim={sim:.3f}"
                        )

                        # Move all articles from cid_b to cid_a
                        cur.execute(
                            "UPDATE articles SET cluster_id = %s WHERE cluster_id = %s;",
                            (cid_a, cid_b),
                        )

                        # Update cluster_articles join table
                        cur.execute(
                            """
                            UPDATE cluster_articles
                            SET cluster_id = %s WHERE cluster_id = %s;
                            """,
                            (cid_a, cid_b),
                        )

                        # Delete the merged cluster
                        cur.execute("DELETE FROM clusters WHERE id = %s;", (cid_b,))

                        merged_into[cid_b] = cid_a
                        merged_count += 1

            conn.commit()

            # Re-synthesize merged clusters
            if merged_count > 0:
                target_clusters = set(merged_into.values())
                _resynthesize_clusters(cur, conn, target_clusters)

            logger.info(f"Cluster merge complete. {merged_count} merges performed.")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error during cluster merge: {e}", exc_info=True)
    finally:
        return_db_connection(conn)

    return {
        "merged": merged_count,
        "timestamp": datetime.datetime.now().isoformat(),
    }


def _resynthesize_clusters(cur, conn, cluster_ids: set):
    """Re-generate synthesized summaries for the given cluster IDs."""
    try:
        llm = get_llm()
    except Exception:
        logger.warning("LLM not available — skipping re-synthesis.")
        return

    for cid in cluster_ids:
        try:
            cur.execute("""
                SELECT a.title, a.summary, s.name, a.published_at
                FROM articles a
                JOIN sources s ON a.source_id = s.id
                WHERE a.cluster_id = %s
                ORDER BY a.published_at DESC;
            """, (cid,))
            articles = cur.fetchall()

            if not articles:
                continue

            # Update outlet count
            unique_outlets = set(art[2] for art in articles)
            outlet_count = len(unique_outlets)

            articles_context = ""
            for idx, (title, summary, s_name, pub_at) in enumerate(articles):
                articles_context += (
                    f"Source {idx + 1}: {s_name}\n"
                    f"Headline: {title}\n"
                    f"Summary: {summary or 'N/A'}\n\n"
                )

            prompt = (
                "You are a professional newspaper editor. Synthesize a unified "
                "report from the following coverage of a single news event.\n"
                "Tasks:\n"
                "1. Create a compelling, professional, neutral unified headline "
                "(do not use clickbait).\n"
                "2. Write a cohesive 2-to-3 sentence summary citing which outlet "
                "reported what key details. Maintain an objective tone.\n\n"
                f"Articles:\n{articles_context}"
                "Respond ONLY with a valid JSON object containing 'headline' "
                "and 'summary' keys."
            )

            structured_llm = llm.with_structured_output(ClusterSynthesis)
            result = structured_llm.invoke([HumanMessage(content=prompt)])

            # Generate summary embedding
            try:
                embeddings_model = get_embeddings()
                summary_text = f"{result.headline}. {result.summary}"
                summary_embedding = embeddings_model.embed_query(summary_text)

                cur.execute(
                    """
                    UPDATE clusters
                    SET headline = %s, synthesized_summary = %s, outlet_count = %s,
                        summary_embedding = %s, last_updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (result.headline, result.summary, outlet_count,
                     summary_embedding, cid),
                )
            except Exception:
                cur.execute(
                    """
                    UPDATE clusters
                    SET headline = %s, synthesized_summary = %s, outlet_count = %s,
                        last_updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (result.headline, result.summary, outlet_count, cid),
                )

            conn.commit()
            logger.info(f"Re-synthesized merged cluster {cid}")

        except Exception as e:
            logger.error(f"Failed to re-synthesize cluster {cid}: {e}")
