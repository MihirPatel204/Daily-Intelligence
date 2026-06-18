"""
Daily Intelligence API — application factory.

Slim entrypoint: lifespan hook for startup/shutdown, CORS middleware,
and router mounting.  All endpoint logic lives in app/routers/.
"""

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db, init_pool, close_pool
from app.services.embedding_service import get_embeddings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def periodic_ingestion():
    """Background loop to poll RSS feeds and run clustering/synthesis periodically."""
    from app.config import settings
    # Let the server finish startup before first run
    await asyncio.sleep(10)

    while True:
        try:
            logger.info("Starting periodic background ingestion...")
            from app.ingest import run_pipeline

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, run_pipeline)
            logger.info(f"Periodic ingestion completed: {result}")
        except Exception as e:
            logger.error(f"Error during periodic ingestion: {e}", exc_info=True)

        # Sleep for configured interval
        await asyncio.sleep(settings.background_ingestion_interval_hours * 3600)


async def periodic_cluster_merge():
    """Background loop to merge similar clusters periodically."""
    from app.config import settings

    # Wait for first ingestion cycle to complete
    await asyncio.sleep(600)

    interval_seconds = settings.cluster_merge_interval_hours * 3600

    while True:
        try:
            logger.info("Starting periodic cluster merge...")
            from app.ingestion.merge import merge_similar_clusters

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, merge_similar_clusters)
            logger.info(f"Cluster merge completed: {result}")
        except Exception as e:
            logger.error(f"Error during cluster merge: {e}", exc_info=True)

        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    logger.info("Starting Daily Intelligence API v2.0 …")

    # Initialize database schema (before pool, since it may need to create tables)
    init_db()

    # Initialize connection pool
    init_pool()

    # Eagerly load the embedding model so the first request isn't slow
    try:
        get_embeddings()
        logger.info("Embedding model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to pre-load embedding model: {e}")

    # Start background tasks
    from app.config import settings
    ingestion_task = None
    if settings.enable_background_ingestion:
        logger.info("Starting periodic background ingestion...")
        ingestion_task = asyncio.create_task(periodic_ingestion())
    else:
        logger.info("Periodic background ingestion is disabled via configuration.")

    merge_task = asyncio.create_task(periodic_cluster_merge())

    yield

    # Shutdown
    logger.info("Shutting down Daily Intelligence API.")
    if ingestion_task:
        ingestion_task.cancel()
    merge_task.cancel()
    close_pool()


app = FastAPI(
    title="Daily Intelligence API",
    description="AI-powered news aggregation with LangChain / LangGraph RAG",
    version="2.0",
    lifespan=lifespan,
)

# CORS — allow any origin/IP to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
from app.routers import clusters, chat, ingest  # noqa: E402

app.include_router(clusters.router, tags=["Clusters"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(ingest.router, tags=["Ingestion"])


@app.get("/api/health")
async def health_check():
    """Health-check endpoint."""
    return {"status": "healthy", "version": "2.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
