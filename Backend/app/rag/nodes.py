"""
RAG Nodes — the three processing steps in the LangGraph RAG workflow.

1. retrieve_node  — Embeds the query and searches pgvector (story-scoped or corpus-wide).
2. grade_node     — Filters irrelevant documents by distance threshold.
3. generate_node  — Builds the RAG prompt and streams the LLM response.

Updated to use DB-backed chat history and cluster-level summary embeddings.
"""

import logging
import datetime
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.config import settings
from app.db import get_db_connection, return_db_connection
from app.services.embedding_service import get_embeddings
from app.services.llm_service import get_llm, clean_llm_content
from app.rag.state import RAGState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1: Retrieve
# ---------------------------------------------------------------------------

def retrieve_node(state: RAGState) -> dict:
    """
    Retrieve relevant documents from the database.

    - Story-scoped (cluster_id set): fetches ALL articles in the cluster.
    - Global (cluster_id is None): pgvector cosine similarity search across
      recent articles AND cluster summaries within the configured time window.
    """
    cluster_id: Optional[int] = state.get("cluster_id")
    question: str = state["question"]

    conn = get_db_connection()
    documents: list[dict] = []

    try:
        with conn.cursor() as cur:
            if cluster_id:
                # Story-scoped retrieval — every article in the cluster
                cur.execute(
                    """
                    SELECT a.title, a.summary, a.url, s.name AS source_name
                    FROM articles a
                    JOIN sources s ON a.source_id = s.id
                    WHERE a.cluster_id = %s
                    ORDER BY a.published_at DESC;
                    """,
                    (cluster_id,),
                )
                for row in cur.fetchall():
                    documents.append({
                        "title": row[0],
                        "summary": row[1] or "",
                        "url": row[2],
                        "source_name": row[3],
                    })
            else:
                # Global retrieval — hybrid: article embeddings + cluster summary embeddings
                embeddings = get_embeddings()
                query_vector = embeddings.embed_query(question)

                cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
                    days=settings.rag_time_window_days
                )

                # Search article embeddings
                cur.execute(
                    """
                    SELECT a.title, a.summary, a.url, s.name AS source_name,
                           a.embedding <=> %s::vector AS distance
                    FROM articles a
                    JOIN sources s ON a.source_id = s.id
                    WHERE a.published_at > %s AND a.embedding IS NOT NULL
                    ORDER BY distance ASC
                    LIMIT %s;
                    """,
                    (query_vector, cutoff, settings.rag_top_k),
                )

                article_results = cur.fetchall()

                # Also search cluster summary embeddings for broader topic matching
                cur.execute(
                    """
                    SELECT c.headline, c.synthesized_summary, c.id,
                           c.summary_embedding <=> %s::vector AS distance
                    FROM clusters c
                    WHERE c.last_updated_at > %s
                      AND c.summary_embedding IS NOT NULL
                    ORDER BY distance ASC
                    LIMIT 3;
                    """,
                    (query_vector, cutoff),
                )
                cluster_results = cur.fetchall()

                # Combine: article results first, then cluster-level context
                for row in article_results:
                    documents.append({
                        "title": row[0],
                        "summary": row[1] or "",
                        "url": row[2],
                        "source_name": row[3],
                        "distance": float(row[4]),
                    })

                # Add cluster summaries as additional context (if not already covered)
                seen_titles = {d["title"] for d in documents}
                for row in cluster_results:
                    if row[0] not in seen_titles:
                        documents.append({
                            "title": row[0],
                            "summary": row[1] or "",
                            "url": f"cluster:{row[2]}",
                            "source_name": "Synthesized Report",
                            "distance": float(row[3]),
                        })

                # Sort combined results by distance
                documents.sort(key=lambda d: d.get("distance", 1.0))
                documents = documents[:settings.rag_top_k + 3]

    except Exception as e:
        logger.error(f"retrieve_node error: {e}", exc_info=True)
    finally:
        return_db_connection(conn)

    logger.info(
        f"Retrieved {len(documents)} documents "
        f"(cluster_id={cluster_id}) for: '{question[:60]}...'"
    )
    return {"documents": documents}


# ---------------------------------------------------------------------------
# Node 2: Grade / Filter
# ---------------------------------------------------------------------------

def grade_node(state: RAGState) -> dict:
    """
    Grade retrieved documents for relevance.

    For story-scoped queries (no distance metric), all documents pass.
    For global queries, documents beyond a distance threshold are dropped,
    but at least the top-3 are always kept.
    """
    documents: list[dict] = state.get("documents", [])

    if not documents:
        return {"documents": []}

    # Story-scoped — keep everything
    if "distance" not in documents[0]:
        return {"documents": documents}

    # Global — filter by distance
    graded = [d for d in documents if d.get("distance", 1.0) < 0.85]

    # Always keep at least top-3
    if len(graded) < 3:
        graded = documents[: min(3, len(documents))]

    logger.info(f"Graded {len(documents)} → {len(graded)} documents")
    return {"documents": graded}


# ---------------------------------------------------------------------------
# Node 3: Generate (async — uses llm.astream for token-level streaming)
# ---------------------------------------------------------------------------

async def generate_node(state: RAGState) -> dict:
    """
    Build the RAG prompt from retrieved context + conversation history
    and stream the LLM response.

    Uses DB-backed chat history for multi-turn persistence.
    """
    llm = get_llm()
    documents: list[dict] = state.get("documents", [])
    question: str = state["question"]
    chat_history = state.get("messages", [])
    cluster_id: Optional[int] = state.get("cluster_id")

    # ----- no context available -------------------------------------------------
    if not documents:
        fallback = (
            "I couldn't find any relevant articles to answer your question. "
            "Please try rephrasing or asking about a different topic."
        )
        return {
            "generation": fallback,
            "citations": [],
            "messages": [HumanMessage(content=question), AIMessage(content=fallback)],
        }

    # ----- build context block --------------------------------------------------
    context_parts = []
    for doc in documents:
        context_parts.append(
            f"Source Publisher: {doc['source_name']}\n"
            f"Title: {doc['title']}\n"
            f"Summary: {doc['summary'] or 'N/A'}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # ----- system prompt varies by scope ----------------------------------------
    if cluster_id:
        system_content = (
            "You are an AI Editorial Assistant for 'The Daily Intelligence'.\n"
            "You are discussing a specific news story cluster. Ground your conversation "
            "ENTIRELY on the provided news reports.\n"
            "For every claim, cite which publisher reported it "
            "(e.g., 'According to NDTV…', 'Reuters reports…').\n"
            "If the question cannot be answered from the provided context, say so clearly.\n"
            "Format your response in clean, readable markdown."
        )
    else:
        system_content = (
            "You are an AI News Intelligence Assistant for 'The Daily Intelligence'.\n"
            "Answer the user's question about recent news using ONLY the provided article context.\n"
            "For every claim, cite which publisher reported it "
            "(e.g., 'BBC reports…', 'According to India Today…').\n"
            "If the context doesn't contain enough information, state that clearly.\n"
            "Format your response in clean, readable markdown."
        )

    # ----- assemble messages ----------------------------------------------------
    prompt_messages: list = [SystemMessage(content=system_content)]

    # Append conversation history (cap at last 10 to prevent token overflow)
    if chat_history:
        prompt_messages.extend(chat_history[-10:])

    prompt_messages.append(
        HumanMessage(
            content=(
                f"News Articles Context:\n\n{context}\n\n"
                f"User Question: {question}"
            )
        )
    )

    # ----- stream LLM response --------------------------------------------------
    full_content = ""
    async for chunk in llm.astream(prompt_messages):
        full_content += clean_llm_content(chunk.content)

    # ----- build citations ------------------------------------------------------
    citations = [
        {"title": d["title"], "url": d["url"], "source_name": d["source_name"]}
        for d in documents
        if not d["url"].startswith("cluster:")  # Don't cite synthesized reports
    ]

    return {
        "generation": full_content,
        "citations": citations,
        "messages": [
            HumanMessage(content=question),
            AIMessage(content=full_content),
        ],
    }
