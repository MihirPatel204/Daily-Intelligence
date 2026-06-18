"""
Ingestion Router — trigger for the RSS fetch / embed / cluster pipeline.
"""

import logging
import traceback
import asyncio
from fastapi import APIRouter, BackgroundTasks

from app.ingest import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/ingest")
@router.get("/api/ingest")
async def trigger_ingestion(background_tasks: BackgroundTasks):
    """Trigger the news ingestion pipeline as a background task."""
    logger.info("Ingestion manually triggered.")
    background_tasks.add_task(run_pipeline)
    return {
        "status": "success",
        "message": "News ingestion triggered in the background.",
    }


@router.get("/api/ingest/debug")
async def debug_ingestion():
    """Run the ingestion pipeline synchronously and return detailed status or errors."""
    from app.db import get_db_connection, return_db_connection

    diagnostic = {}

    # 1. Check DB connection and table counts
    try:
        conn = get_db_connection(register=False)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sources;")
            sources_count = cur.fetchone()[0]
            cur.execute("SELECT id, name, active FROM sources;")
            sources_list = [
                {"id": s[0], "name": s[1], "active": s[2]} for s in cur.fetchall()
            ]

            cur.execute("SELECT COUNT(*) FROM articles;")
            articles_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM clusters;")
            clusters_count = cur.fetchone()[0]

            diagnostic["db"] = {
                "connection": "ok",
                "sources_count": sources_count,
                "sources": sources_list,
                "articles_count": articles_count,
                "clusters_count": clusters_count,
            }
        return_db_connection(conn)
    except Exception as e:
        diagnostic["db"] = {
            "connection": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

    # 2. Run pipeline synchronously (offloaded to thread)
    try:
        logger.info("Running pipeline synchronously for debugging...")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_pipeline)
        diagnostic["pipeline"] = {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Debug pipeline execution failed: {e}", exc_info=True)
        diagnostic["pipeline"] = {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

    return diagnostic


@router.get("/api/ingest/status")
async def get_ingest_status():
    """Retrieve database counts for diagnosing ingestion progress."""
    from app.db import get_db_connection, return_db_connection

    diagnostic = {}
    try:
        conn = get_db_connection(register=False)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sources;")
            sources_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM articles;")
            articles_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM clusters;")
            clusters_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM articles WHERE embedding IS NULL;")
            unembedded_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM articles WHERE cluster_id IS NULL;")
            unclustered_count = cur.fetchone()[0]

            diagnostic["db"] = {
                "connection": "ok",
                "sources_count": sources_count,
                "articles_count": articles_count,
                "clusters_count": clusters_count,
                "unembedded_count": unembedded_count,
                "unclustered_count": unclustered_count,
            }
        return_db_connection(conn)
    except Exception as e:
        diagnostic["db"] = {
            "connection": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    return diagnostic


@router.get("/api/ingest/config")
async def get_ingest_config():
    """Retrieve backend configuration for diagnosing environment variables."""
    from app.config import settings

    # Mask password in connection string
    db_url = settings.database_url
    if "@" in db_url:
        parts = db_url.split("@")
        masked_conn = parts[0].split(":")[0] + "://***:***@" + parts[1]
    else:
        masked_conn = db_url
    return {
        "database_url": masked_conn,
        "vector_dimensions": settings.vector_dimensions,
        "embedding_model": settings.embedding_model,
        "gemini_model": settings.gemini_model,
    }
