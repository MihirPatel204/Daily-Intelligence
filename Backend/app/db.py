"""
Database — connection pool, schema initialization, and seed data.

Uses ThreadedConnectionPool for connection reuse instead of per-call connects.
Adds cluster_articles join table and chat_messages table per PRD §7.
"""

import logging
import atexit
import psycopg2
from psycopg2 import pool as pg_pool

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection Pool
# ---------------------------------------------------------------------------

_connection_pool: pg_pool.ThreadedConnectionPool | None = None


def init_pool():
    """Initialize the ThreadedConnectionPool. Call once at startup."""
    global _connection_pool
    if _connection_pool is not None:
        return

    if not settings.database_url:
        raise ValueError("DATABASE_URL environment variable is not set.")

    _connection_pool = pg_pool.ThreadedConnectionPool(
        minconn=settings.db_pool_min,
        maxconn=settings.db_pool_max,
        dsn=settings.database_url,
    )
    logger.info(
        f"Connection pool initialized (min={settings.db_pool_min}, max={settings.db_pool_max})."
    )


def close_pool():
    """Close all connections in the pool. Call at shutdown."""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Connection pool closed.")


# Close pool on process exit as a safety net
atexit.register(close_pool)


def get_db_connection(register=True):
    """
    Return a connection from the pool.

    If the pool hasn't been initialized yet (e.g. during init_db before lifespan),
    falls back to a direct psycopg2.connect().

    Args:
        register: Whether to register the pgvector type on this connection.
    """
    global _connection_pool

    if _connection_pool is not None:
        conn = _connection_pool.getconn()
    else:
        if not settings.database_url:
            raise ValueError("DATABASE_URL environment variable is not set.")
        conn = psycopg2.connect(settings.database_url)

    # Set statement timeout to prevent locks from hanging
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 15000;")

    if register:
        from pgvector.psycopg2 import register_vector
        register_vector(conn)

    return conn


def return_db_connection(conn):
    """Return a connection back to the pool."""
    global _connection_pool
    if _connection_pool is not None:
        try:
            _connection_pool.putconn(conn)
        except Exception:
            # If putconn fails, close directly
            try:
                conn.close()
            except Exception:
                pass
    else:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Curated seed sources
# ---------------------------------------------------------------------------

SEED_SOURCES = [
    # Indian News Media
    {"name": "NDTV Top Stories", "rss_url": "https://feeds.feedburner.com/ndtvnews-top-stories", "category": "India"},
    {"name": "Times of India", "rss_url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "category": "India"},
    {"name": "India Today", "rss_url": "https://www.indiatoday.in/rss/home", "category": "India"},
    {"name": "The Hindu", "rss_url": "https://www.thehindu.com/news/feeder/default.rss", "category": "India"},
    # Global News Media
    {"name": "BBC News World", "rss_url": "http://feeds.bbci.co.uk/news/world/rss.xml", "category": "World"},
    {"name": "CNN Top Stories", "rss_url": "http://rss.cnn.com/rss/edition.rss", "category": "World"},
    {"name": "TechCrunch", "rss_url": "https://techcrunch.com/feed/", "category": "Tech"},
    {"name": "CNBC Business", "rss_url": "https://search.cnbc.com/rs/search/combinedfeed.cxml", "category": "Business"},
]


# ---------------------------------------------------------------------------
# Schema initialization
# ---------------------------------------------------------------------------

def init_db():
    """Initialize the database schema and seed initial sources."""
    conn = None
    try:
        # Connect without registering the vector type first
        conn = get_db_connection(register=False)
        with conn.cursor() as cur:
            # Enable pgvector extension
            logger.info("Enabling pgvector extension...")
            try:
                cur.execute("SET statement_timeout = 5000;")
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
            except Exception as ext_err:
                conn.rollback()
                logger.warning(
                    f"Could not CREATE EXTENSION vector (it may already exist): {ext_err}"
                )

        # Register the vector type now
        from pgvector.psycopg2 import register_vector
        register_vector(conn)

        with conn.cursor() as cur:
            # --- sources ---
            logger.info("Creating sources table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    rss_url VARCHAR(255) UNIQUE NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    active BOOLEAN DEFAULT TRUE
                );
            """)

            # --- clusters ---
            logger.info("Creating clusters table...")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS clusters (
                    id SERIAL PRIMARY KEY,
                    headline TEXT NOT NULL,
                    synthesized_summary TEXT,
                    category VARCHAR(50) NOT NULL,
                    score DOUBLE PRECISION DEFAULT 0.0,
                    size_tier VARCHAR(20) DEFAULT 'standard',
                    outlet_count INTEGER DEFAULT 0,
                    summary_embedding vector({settings.vector_dimensions}),
                    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # --- articles ---
            logger.info("Creating articles table...")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS articles (
                    id SERIAL PRIMARY KEY,
                    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
                    url VARCHAR(512) UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    published_at TIMESTAMP WITH TIME ZONE,
                    image_url TEXT,
                    raw_text TEXT,
                    embedding vector({settings.vector_dimensions}),
                    cluster_id INTEGER REFERENCES clusters(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # --- cluster_articles join table (PRD §7) ---
            logger.info("Creating cluster_articles join table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cluster_articles (
                    cluster_id INTEGER REFERENCES clusters(id) ON DELETE CASCADE,
                    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
                    PRIMARY KEY (cluster_id, article_id)
                );
            """)

            # --- chat_messages (PRD §7) ---
            logger.info("Creating chat_messages table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) NOT NULL,
                    cluster_id INTEGER REFERENCES clusters(id) ON DELETE SET NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # --- Indexes ---
            # HNSW index for article embeddings
            if settings.vector_dimensions <= 2000:
                logger.info("Creating HNSW index for articles...")
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS articles_embedding_idx "
                    "ON articles USING hnsw (embedding vector_cosine_ops);"
                )
            else:
                logger.info(
                    "Vector dimensions > 2000; skipping HNSW index (using IVFFlat or sequential scan)."
                )

            # Index on chat_messages for session lookups
            cur.execute(
                "CREATE INDEX IF NOT EXISTS chat_messages_session_idx "
                "ON chat_messages (session_id, created_at);"
            )

            # Index on cluster_articles for cluster lookups
            cur.execute(
                "CREATE INDEX IF NOT EXISTS cluster_articles_cluster_idx "
                "ON cluster_articles (cluster_id);"
            )

            # --- Seed sources if empty ---
            cur.execute("SELECT COUNT(*) FROM sources;")
            count = cur.fetchone()[0]
            if count == 0:
                logger.info("Seeding news sources...")
                for source in SEED_SOURCES:
                    cur.execute(
                        "INSERT INTO sources (name, rss_url, category) "
                        "VALUES (%s, %s, %s) ON CONFLICT (rss_url) DO NOTHING;",
                        (source["name"], source["rss_url"], source["category"]),
                    )

            # --- Add summary_embedding column if it doesn't exist (migration) ---
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'clusters' AND column_name = 'summary_embedding';
            """)
            if not cur.fetchone():
                logger.info("Adding summary_embedding column to clusters...")
                cur.execute(f"""
                    ALTER TABLE clusters
                    ADD COLUMN summary_embedding vector({settings.vector_dimensions});
                """)

            conn.commit()
            logger.info("Database initialized successfully.")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        if conn:
            return_db_connection(conn)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
