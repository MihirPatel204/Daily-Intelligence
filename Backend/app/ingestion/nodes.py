"""
Ingestion Nodes — processing steps for the LangGraph ingestion pipeline.

Each function is a node in the StateGraph, receiving IngestionState and
returning a partial state update dict.

Pipeline: fetch → parse_dedupe → embed → cluster_match → [verify] →
          score → summarize → [critique] → store
"""

import re
import html
import logging
import datetime
import socket
from typing import List, Dict, Any, Optional

# Set default socket timeout to prevent hanging on slow RSS feeds
socket.setdefaulttimeout(15.0)

import numpy as np
import feedparser
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.config import settings
from app.db import get_db_connection, return_db_connection
from app.services.embedding_service import get_embeddings
from app.services.llm_service import get_llm, clean_llm_content
from app.ingestion.state import IngestionState, ArticleData, ClusterData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema for structured LLM output
# ---------------------------------------------------------------------------

class ClusterSynthesis(BaseModel):
    headline: str
    summary: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def extract_image_url(entry: Any) -> Optional[str]:
    """Try to extract an image URL from an RSS entry."""
    for media_key in ['media_content', 'media_thumbnail', 'enclosures']:
        if hasattr(entry, media_key) and getattr(entry, media_key):
            media_list = getattr(entry, media_key)
            if isinstance(media_list, list) and len(media_list) > 0:
                item = media_list[0]
                if isinstance(item, dict) and 'url' in item:
                    return item['url']
                elif hasattr(item, 'url'):
                    return getattr(item, 'url')

    content = ""
    if hasattr(entry, 'description') and entry.description:
        content += entry.description
    if hasattr(entry, 'content') and entry.content:
        for c in entry.content:
            if isinstance(c, dict) and 'value' in c:
                content += c['value']
            elif hasattr(c, 'value'):
                content += getattr(c, 'value')

    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        return img_match.group(1)

    return None


def cosine_similarity(v1, v2) -> float:
    """Compute cosine similarity between two vectors."""
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


# ---------------------------------------------------------------------------
# Node 1: FETCH — Poll RSS feeds and insert new articles
# ---------------------------------------------------------------------------

def fetch_node(state: IngestionState) -> dict:
    """
    Poll each active source's RSS feed, parse entries, and insert new
    articles into the database. Per-source failures are isolated.
    """
    logger.info("=== FETCH NODE: Polling RSS feeds ===")
    conn = get_db_connection()
    new_articles: List[ArticleData] = []
    errors: List[str] = state.get("errors", [])

    try:
        with conn.cursor() as cur:
            # 1. Clean up stale unclustered articles older than 24 hours to prevent backlog build-up
            cur.execute("""
                DELETE FROM articles 
                WHERE cluster_id IS NULL AND created_at < NOW() - INTERVAL '24 hours';
            """)
            conn.commit()

            cur.execute(
                "SELECT id, name, rss_url, category FROM sources WHERE active = TRUE;"
            )
            sources = cur.fetchall()

        for source_id, source_name, rss_url, category in sources:
            logger.info(f"Fetching RSS: {source_name}")
            try:
                feed = feedparser.parse(rss_url)
                # Limit to top 5 entries per feed to only get the most important/fresh breaking news
                entries_to_process = feed.entries[:5]
                for entry in entries_to_process:
                    title = clean_html(getattr(entry, 'title', ''))
                    summary = clean_html(getattr(entry, 'summary', ''))
                    if not summary and hasattr(entry, 'description'):
                        summary = clean_html(entry.description)

                    link = getattr(entry, 'link', '')
                    if not title or not link:
                        continue

                    # Parse published time
                    pub_time = datetime.datetime.now(datetime.timezone.utc)
                    for time_key in ['published_parsed', 'updated_parsed']:
                        if hasattr(entry, time_key) and getattr(entry, time_key):
                            struct_time = getattr(entry, time_key)
                            pub_time = datetime.datetime(
                                *struct_time[:6], tzinfo=datetime.timezone.utc
                            )
                            break

                    image_url = extract_image_url(entry)

                    # Insert with deduplication
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT 1 FROM articles WHERE url = %s;", (link,)
                        )
                        if not cur.fetchone():
                            try:
                                cur.execute(
                                    """
                                    INSERT INTO articles
                                        (source_id, url, title, summary, published_at, image_url)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    RETURNING id;
                                    """,
                                    (source_id, link, title, summary, pub_time, image_url),
                                )
                                row = cur.fetchone()
                                if row:
                                    conn.commit()
                                    new_articles.append(
                                        ArticleData(
                                            id=row[0],
                                            source_id=source_id,
                                            source_name=source_name,
                                            source_category=category,
                                            url=link,
                                            title=title,
                                            summary=summary,
                                            published_at=pub_time.isoformat(),
                                            image_url=image_url,
                                        )
                                    )
                            except Exception as insert_err:
                                logger.error(
                                    f"Failed to insert article {link}: {insert_err}"
                                )
                                conn.rollback()
            except Exception as e:
                error_msg = f"Error parsing feed {source_name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

    except Exception as e:
        error_msg = f"Database error during RSS fetch: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
    finally:
        return_db_connection(conn)

    logger.info(f"Fetch complete. {len(new_articles)} new articles inserted.")
    return {
        "new_articles": new_articles,
        "fetch_count": len(new_articles),
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 2: EMBED — Generate embeddings for un-embedded articles
# ---------------------------------------------------------------------------

def embed_node(state: IngestionState) -> dict:
    """
    Generate embeddings for all articles that don't have one yet.
    Uses batch embedding. If a batch fails, skip it (no retry per user preference).
    """
    logger.info("=== EMBED NODE: Generating embeddings ===")
    conn = get_db_connection()
    errors: List[str] = state.get("errors", [])
    embed_count = 0

    try:
        with conn.cursor() as cur:
            # Limit to 15 articles per run to stay well within Gemini API rate limits
            cur.execute(
                "SELECT id, title, summary FROM articles WHERE embedding IS NULL LIMIT 15;"
            )
            unembedded = cur.fetchall()

            if not unembedded:
                logger.info("No un-embedded articles found.")
                return {"embed_count": 0, "errors": errors}

            embeddings_model = get_embeddings()
            batch_size = settings.embedding_batch_size

            # Process in batches
            for i in range(0, len(unembedded), batch_size):
                batch = unembedded[i : i + batch_size]
                texts = [f"{title}. {summary or ''}" for _, title, summary in batch]
                ids = [art_id for art_id, _, _ in batch]

                try:
                    vectors = embeddings_model.embed_documents(texts)

                    for art_id, vector in zip(ids, vectors):
                        cur.execute(
                            "UPDATE articles SET embedding = %s WHERE id = %s;",
                            (vector, art_id),
                        )
                    conn.commit()
                    embed_count += len(batch)
                    logger.info(
                        f"Embedded batch {i // batch_size + 1}: "
                        f"{len(batch)} articles"
                    )
                except Exception as batch_err:
                    conn.rollback()
                    error_msg = (
                        f"Embedding batch {i // batch_size + 1} failed, skipping: "
                        f"{batch_err}"
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)

    except Exception as e:
        error_msg = f"Error in embed_node: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
    finally:
        return_db_connection(conn)

    logger.info(f"Embedding complete. {embed_count} articles embedded.")
    return {"embed_count": embed_count, "errors": errors}


# ---------------------------------------------------------------------------
# Node 3: CLUSTER MATCH — Assign articles to clusters by similarity
# ---------------------------------------------------------------------------

def cluster_match_node(state: IngestionState) -> dict:
    """
    Match unclustered articles to existing clusters by cosine similarity.
    Calculations and LLM verifications are done in-memory to avoid holding DB transaction locks.
    Once completed, updates are committed to the DB in a single fast transaction.
    """
    logger.info("=== CLUSTER MATCH NODE: Clustering articles ===")
    conn = get_db_connection()
    errors: List[str] = state.get("errors", [])
    cluster_count = 0

    unclustered = []
    clustered_data = []

    # 1. Read all needed data and close cursor/transaction immediately
    try:
        with conn.cursor() as cur:
            # Fetch unclustered articles with embeddings, limiting to 15 to stay within Gemini API rate limits
            cur.execute("""
                SELECT a.id, a.title, a.summary, a.embedding, s.category
                FROM articles a
                JOIN sources s ON a.source_id = s.id
                WHERE a.cluster_id IS NULL AND a.embedding IS NOT NULL
                LIMIT 15;
            """)
            unclustered = cur.fetchall()

            if unclustered:
                # Fetch active clusters from the last 36 hours
                cur.execute("""
                    SELECT c.id, c.headline, c.category, a.embedding, a.title
                    FROM clusters c
                    JOIN articles a ON a.cluster_id = c.id
                    WHERE c.last_updated_at > NOW() - INTERVAL '36 hours';
                """)
                clustered_data = cur.fetchall()
        
        # Commit read operations to close the transaction
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        error_msg = f"Error reading data for clustering: {e}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)
        return_db_connection(conn)
        return {"cluster_count": 0, "errors": errors}

    if not unclustered:
        logger.info("No articles need clustering.")
        return_db_connection(conn)
        return {"cluster_count": 0, "errors": errors}

    # 2. Build active clusters representation in memory
    active_clusters: Dict[int, dict] = {}
    for cid, headline, category, emb, title in clustered_data:
        if isinstance(emb, str):
            emb = [float(x) for x in emb.strip('[]').split(',')]

        if cid not in active_clusters:
            active_clusters[cid] = {
                "headline": headline,
                "category": category,
                "embeddings": [],
                "titles": [],
            }
        active_clusters[cid]["embeddings"].append(np.array(emb))
        active_clusters[cid]["titles"].append(title)

    # 3. Perform matching and verification completely in memory
    assignments = []  # list of (art_id, cluster_id)
    new_clusters_to_create = {}  # temp_cid -> (headline, category, embedding, title)
    next_temp_id = -1

    for art_id, title, summary, art_emb, category in unclustered:
        if isinstance(art_emb, str):
            art_emb = [float(x) for x in art_emb.strip('[]').split(',')]
        art_emb_np = np.array(art_emb)

        matched_cluster_id = None
        best_similarity = 0.0

        for cid, cdata in active_clusters.items():
            centroid = np.mean(cdata["embeddings"], axis=0)
            sim = cosine_similarity(art_emb_np, centroid)
            if sim > best_similarity:
                best_similarity = sim
                matched_cluster_id = cid

        # Threshold logic
        if best_similarity >= settings.cluster_similarity_threshold:
            logger.info(
                f"Article '{title[:50]}' matched cluster "
                f"{matched_cluster_id} (sim={best_similarity:.2f})"
            )
        elif best_similarity >= settings.cluster_ambiguous_threshold:
            # Ambiguous — ask LLM to verify
            cluster_headline = active_clusters[matched_cluster_id]["headline"]
            verified = _verify_cluster_match(
                title, cluster_headline, max_retries=settings.cluster_verify_max_retries
            )
            if verified:
                logger.info(
                    f"Article '{title[:50]}' matched cluster {matched_cluster_id} via LLM"
                )
            else:
                matched_cluster_id = None
        else:
            matched_cluster_id = None

        if matched_cluster_id:
            # Assign to existing cluster in-memory
            assignments.append((art_id, matched_cluster_id))
            active_clusters[matched_cluster_id]["embeddings"].append(art_emb_np)
            active_clusters[matched_cluster_id]["titles"].append(title)
        else:
            # Record creation of new cluster in-memory
            temp_cid = next_temp_id
            next_temp_id -= 1
            logger.info(f"New cluster in-memory for: '{title[:60]}'")
            
            new_clusters_to_create[temp_cid] = {
                "headline": title,
                "category": category,
                "embedding": art_emb_np,
                "title": title
            }
            
            assignments.append((art_id, temp_cid))
            active_clusters[temp_cid] = {
                "headline": title,
                "category": category,
                "embeddings": [art_emb_np],
                "titles": [title],
            }

    # 4. Open a single database transaction and write all results instantly
    try:
        with conn.cursor() as cur:
            temp_to_real_cid = {}

            # Create new clusters in database
            for temp_cid, cinfo in new_clusters_to_create.items():
                cur.execute(
                    """
                    INSERT INTO clusters
                        (headline, category, score, size_tier, outlet_count,
                         first_seen_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING id;
                    """,
                    (cinfo["headline"], cinfo["category"], 10.0, 'brief', 1),
                )
                real_cid = cur.fetchone()[0]
                temp_to_real_cid[temp_cid] = real_cid
                cluster_count += 1

            # Update articles and insert into join table
            for art_id, cid in assignments:
                # If it was a temporary ID, resolve it to the database ID
                real_cid = temp_to_real_cid.get(cid, cid)

                cur.execute(
                    "UPDATE articles SET cluster_id = %s WHERE id = %s;",
                    (real_cid, art_id),
                )
                cur.execute(
                    """
                    INSERT INTO cluster_articles (cluster_id, article_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (real_cid, art_id),
                )
                cur.execute(
                    "UPDATE clusters SET last_updated_at = NOW() WHERE id = %s;",
                    (real_cid,),
                )

        conn.commit()
        logger.info(f"Clustering write transaction committed. {cluster_count} new clusters created.")
    except Exception as e:
        if conn:
            conn.rollback()
        error_msg = f"Error saving clustering results: {e}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)
    finally:
        return_db_connection(conn)

    return {"cluster_count": cluster_count, "errors": errors}


def _verify_cluster_match(
    title1: str, title2: str, max_retries: int = 2
) -> bool:
    """
    Ask the LLM if two headlines describe the same event.
    Bounded by max_retries — if LLM fails, default to 'not a match'.
    """
    for attempt in range(max_retries):
        try:
            import time
            time.sleep(1.0)  # Sleep 1s to respect Gemini API 15 RPM limits
            llm = get_llm()
            prompt = (
                "You are an expert news editor. Analyze these two headlines and determine "
                "if they describe the exact same news story or event.\n"
                "They do not need to share the exact same opinion, but they must cover the same "
                "event (e.g. the same summit, the same accident, the same policy release).\n\n"
                f"Headline 1: {title1}\n"
                f"Headline 2: {title2}\n\n"
                "Reply with YES if they cover the same event, or NO if they are separate events. "
                "Output exactly one word (YES or NO)."
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            answer = clean_llm_content(response.content).strip().upper()
            logger.info(
                f"LLM cluster verify (attempt {attempt + 1}): "
                f"'{title1[:40]}' vs '{title2[:40]}': {answer}"
            )
            return "YES" in answer
        except Exception as e:
            logger.error(f"LLM verify attempt {attempt + 1} failed: {e}")

    logger.warning("LLM verify exhausted retries, defaulting to no-match.")
    return False


# ---------------------------------------------------------------------------
# Node 4: SCORE — Compute importance scores for active clusters
# ---------------------------------------------------------------------------

def score_node(state: IngestionState) -> dict:
    """
    Recompute importance scores for all recently-updated clusters.
    Uses the PRD §10 formula: outlet_count * recency_decay * category_weight.
    Maps scores to percentile-based tiers.
    """
    logger.info("=== SCORE NODE: Computing importance scores ===")
    conn = get_db_connection()
    errors: List[str] = state.get("errors", [])

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, headline, first_seen_at, category FROM clusters
                WHERE last_updated_at > NOW() - INTERVAL '36 hours';
            """)
            active_clusters = cur.fetchall()

            if not active_clusters:
                return {"errors": errors}

            scores: List[tuple] = []

            for cid, headline, first_seen, category in active_clusters:
                # Count distinct outlets covering this cluster
                cur.execute("""
                    SELECT COUNT(DISTINCT s.id)
                    FROM articles a
                    JOIN sources s ON a.source_id = s.id
                    WHERE a.cluster_id = %s;
                """, (cid,))
                outlet_count = cur.fetchone()[0]

                # Recency decay
                hours_since_first = (
                    datetime.datetime.now(datetime.timezone.utc) - first_seen
                ).total_seconds() / 3600.0
                decay_factor = 0.85 ** (hours_since_first / 12.0)

                # Category weight from config
                cat_weight = settings.category_weights.get(category, 1.0)

                # Final score
                score = (outlet_count * 10.0) * decay_factor * cat_weight
                scores.append((cid, score, outlet_count))

                cur.execute(
                    """
                    UPDATE clusters
                    SET score = %s, outlet_count = %s
                    WHERE id = %s;
                    """,
                    (score, outlet_count, cid),
                )

            # Percentile-based tier assignment
            if scores:
                all_scores = sorted([s[1] for s in scores], reverse=True)
                for cid, score, outlet_count in scores:
                    rank = all_scores.index(score)
                    percentile = rank / max(len(all_scores), 1)

                    if percentile < 0.10:
                        size_tier = "lead"
                    elif percentile < 0.30:
                        size_tier = "major"
                    elif percentile < 0.70:
                        size_tier = "standard"
                    else:
                        size_tier = "brief"

                    cur.execute(
                        "UPDATE clusters SET size_tier = %s WHERE id = %s;",
                        (size_tier, cid),
                    )

            conn.commit()
            logger.info(f"Scoring complete for {len(active_clusters)} clusters.")

    except Exception as e:
        if conn:
            conn.rollback()
        error_msg = f"Error during scoring: {e}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)
    finally:
        return_db_connection(conn)

    return {"errors": errors}


# ---------------------------------------------------------------------------
# Node 5: SUMMARIZE — Generate synthesized summaries via LLM
# ---------------------------------------------------------------------------

def summarize_node(state: IngestionState) -> dict:
    """
    Generate or regenerate synthesized headlines and summaries for active clusters.
    Includes a critique loop: if the critique node rejects the summary, this node
    is re-invoked with critique_feedback in state.
    """
    logger.info("=== SUMMARIZE NODE: Generating cluster summaries ===")
    conn = get_db_connection()
    errors: List[str] = state.get("errors", [])
    synthesize_count = 0

    try:
        llm = get_llm()
    except Exception:
        llm = None
        logger.warning("LLM not available — using fallback summaries.")

    active_clusters = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, headline, first_seen_at, category FROM clusters
                WHERE last_updated_at > NOW() - INTERVAL '36 hours';
            """)
            active_clusters = cur.fetchall()
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        error_msg = f"Error fetching active clusters: {e}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)
        return_db_connection(conn)
        return {
            "synthesize_count": 0,
            "critique_feedback": "",
            "errors": errors,
        }

    for cid, headline, first_seen, category in active_clusters:
        articles = []
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.title, a.summary, s.name, a.published_at
                    FROM articles a
                    JOIN sources s ON a.source_id = s.id
                    WHERE a.cluster_id = %s
                    ORDER BY a.published_at DESC;
                """, (cid,))
                articles = cur.fetchall()
            conn.commit()
        except Exception as read_err:
            if conn:
                conn.rollback()
            logger.error(f"Error fetching articles for cluster {cid}: {read_err}")
            continue

        if not articles:
            continue

        # Default fallback
        syn_headline = headline
        syn_summary = articles[0][1] or articles[0][0]

        if llm and articles:
            articles_context = ""
            for idx, (title, summary, s_name, pub_at) in enumerate(articles):
                articles_context += (
                    f"Source {idx + 1}: {s_name}\n"
                    f"Headline: {title}\n"
                    f"Summary: {summary or 'N/A'}\n\n"
                )

            # Include critique feedback if this is a retry
            critique_feedback = state.get("critique_feedback", "")
            feedback_section = ""
            if critique_feedback and state.get("current_cluster_id") == cid:
                feedback_section = (
                    f"\n\nPREVIOUS ATTEMPT FEEDBACK: {critique_feedback}\n"
                    "Please address the feedback in your revised summary.\n"
                )

            prompt = (
                "You are a professional newspaper editor. Synthesize a unified "
                "report from the following coverage of a single news event.\n"
                "Tasks:\n"
                "1. Create a compelling, professional, neutral unified headline "
                "(do not use clickbait).\n"
                "2. Write a cohesive 2-to-3 sentence summary citing which outlet "
                "reported what key details (e.g., 'BBC reports… while NDTV adds…'). "
                "Maintain an objective tone.\n\n"
                f"Articles:\n{articles_context}"
                f"{feedback_section}"
                "Respond ONLY with a valid JSON object containing 'headline' "
                "and 'summary' keys."
            )

            try:
                import time
                time.sleep(1.5)  # Sleep 1.5s to respect Gemini API 15 RPM limits

                from langchain_core.output_parsers import JsonOutputParser
                parser = JsonOutputParser(pydantic_object=ClusterSynthesis)
                
                format_instructions = parser.get_format_instructions()
                full_prompt = f"{prompt}\n\n{format_instructions}"

                chain = llm | parser
                result = chain.invoke([HumanMessage(content=full_prompt)])

                if result is None:
                    raise ValueError("LLM returned None for structured output")

                syn_headline = result.get("headline", headline)
                syn_summary = result.get("summary")
                if not syn_summary:
                    syn_summary = articles[0][1] or articles[0][0]
                synthesize_count += 1
            except Exception as e:
                logger.error(
                    f"LLM synthesis failed for cluster {cid}: {e}. "
                    "Using fallback."
                )

        # Generate summary embedding for cluster-level retrieval
        summary_embedding = None
        try:
            embeddings_model = get_embeddings()
            summary_text = f"{syn_headline}. {syn_summary}"
            summary_embedding = embeddings_model.embed_query(summary_text)
        except Exception as emb_err:
            logger.error(
                f"Failed to generate embedding for cluster summary {cid}: {emb_err}"
            )

        # Update cluster in database inside a short transaction
        try:
            with conn.cursor() as cur:
                if summary_embedding is not None:
                    cur.execute(
                        """
                        UPDATE clusters
                        SET headline = %s, synthesized_summary = %s,
                            summary_embedding = %s
                        WHERE id = %s;
                        """,
                        (syn_headline, syn_summary, summary_embedding, cid),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE clusters
                        SET headline = %s, synthesized_summary = %s
                        WHERE id = %s;
                        """,
                        (syn_headline, syn_summary, cid),
                    )
            conn.commit()
            logger.info(f"Successfully synthesized and committed cluster {cid}")
        except Exception as write_err:
            if conn:
                conn.rollback()
            logger.error(
                f"Failed to write synthesized summary/embedding for cluster {cid}: {write_err}"
            )
            errors.append(f"Write failed for cluster {cid}: {write_err}")

    logger.info(
        f"Synthesis complete. {synthesize_count} clusters summarized via LLM."
    )
    return_db_connection(conn)

    return {
        "synthesize_count": synthesize_count,
        "critique_feedback": "",
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 6: CRITIQUE — Quality-check summaries against source articles
# ---------------------------------------------------------------------------

def critique_node(state: IngestionState) -> dict:
    """
    Check the most recently synthesized summaries for unsupported claims.
    If a summary fails the critique, set critique_feedback so the graph
    loops back to summarize_node.
    """
    logger.info("=== CRITIQUE NODE: Checking summary quality ===")
    conn = get_db_connection()
    errors: List[str] = state.get("errors", [])
    critique_retry_count = state.get("critique_retry_count", 0)

    # Skip critique if we've exceeded max retries
    if critique_retry_count >= settings.summary_critique_max_retries:
        logger.info("Max critique retries reached, accepting current summaries.")
        return {
            "critique_feedback": "",
            "critique_retry_count": 0,
            "errors": errors,
        }

    try:
        llm = get_llm()

        with conn.cursor() as cur:
            # Check summaries updated in the last 5 minutes
            cur.execute("""
                SELECT id, headline, synthesized_summary FROM clusters
                WHERE last_updated_at > NOW() - INTERVAL '5 minutes'
                AND synthesized_summary IS NOT NULL;
            """)
            recent_clusters = cur.fetchall()

            for cid, headline, summary in recent_clusters:
                cur.execute("""
                    SELECT a.title, a.summary, s.name
                    FROM articles a
                    JOIN sources s ON a.source_id = s.id
                    WHERE a.cluster_id = %s;
                """, (cid,))
                articles = cur.fetchall()

                if not articles:
                    continue

                source_snippets = "\n".join(
                    f"- {s_name}: {a_title}. {a_summary or ''}"
                    for a_title, a_summary, s_name in articles
                )

                prompt = (
                    "You are a fact-checking editor. Compare this synthesized summary "
                    "against the source articles and identify any claims NOT supported "
                    "by the sources.\n\n"
                    f"SYNTHESIZED HEADLINE: {headline}\n"
                    f"SYNTHESIZED SUMMARY: {summary}\n\n"
                    f"SOURCE ARTICLES:\n{source_snippets}\n\n"
                    "If the summary is accurate and well-grounded, respond with exactly: PASS\n"
                    "If there are issues, respond with a brief description of what needs fixing."
                )

                try:
                    response = llm.invoke([HumanMessage(content=prompt)])
                    answer = clean_llm_content(response.content).strip()

                    if "PASS" not in answer.upper():
                        logger.warning(
                            f"Critique failed for cluster {cid}: {answer[:100]}"
                        )
                        return {
                            "critique_feedback": answer,
                            "current_cluster_id": cid,
                            "critique_retry_count": critique_retry_count + 1,
                            "errors": errors,
                        }
                    else:
                        logger.info(f"Critique passed for cluster {cid}")
                except Exception as e:
                    logger.error(f"Critique LLM call failed for cluster {cid}: {e}")

    except Exception as e:
        error_msg = f"Error in critique node: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
    finally:
        return_db_connection(conn)

    return {
        "critique_feedback": "",
        "critique_retry_count": 0,
        "errors": errors,
    }
