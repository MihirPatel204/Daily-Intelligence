"""
RAG Service — high-level interface for streaming RAG responses.

This is the entry-point that routers call.  It invokes the LangGraph RAG
graph via ``astream_events`` and yields SSE-formatted strings suitable for
FastAPI's ``StreamingResponse``.

Chat messages are persisted to the database for multi-session history.
"""

import json
import logging
from typing import AsyncGenerator, Optional

from app.rag.graph import get_rag_graph
from app.services.chat_history_service import save_message

logger = logging.getLogger(__name__)


async def stream_rag_response(
    question: str,
    session_id: str,
    cluster_id: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a RAG response as Server-Sent Events.

    Yields SSE ``data:`` lines with JSON payloads:
    - ``{"type": "token",     "content": "..."}``  — streamed LLM tokens
    - ``{"type": "citations", "citations": [...]}`` — source citations
    - ``[DONE]``                                    — terminal sentinel

    Persists user and AI messages to the chat_messages table.
    """
    graph = get_rag_graph()
    config = {"configurable": {"thread_id": session_id}}

    initial_state = {
        "question": question,
        "cluster_id": cluster_id,
        "documents": [],
        "generation": "",
        "citations": [],
    }

    collected_citations: list[dict] = []
    has_streamed = False
    final_generation = ""

    # Persist the user message
    save_message(
        session_id=session_id,
        role="human",
        content=question,
        cluster_id=cluster_id,
    )

    try:
        async for event in graph.astream_events(
            initial_state, config=config, version="v2"
        ):
            kind = event["event"]

            # ---- token-level streaming from the LLM ----
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = getattr(chunk, "content", "")
                if content:
                    has_streamed = True
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

            # ---- capture final node output for citations ----
            elif kind == "on_chain_end":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    if "citations" in output:
                        collected_citations = output["citations"]
                    if "generation" in output:
                        final_generation = output["generation"]

        # Fallback: if streaming tokens didn't fire, send the full generation
        if not has_streamed and final_generation:
            yield f"data: {json.dumps({'type': 'token', 'content': final_generation})}\n\n"

        # Send citations
        yield f"data: {json.dumps({'type': 'citations', 'citations': collected_citations})}\n\n"

        # Persist the AI response
        if final_generation:
            save_message(
                session_id=session_id,
                role="ai",
                content=final_generation,
                cluster_id=cluster_id,
            )

    except Exception as e:
        logger.error(f"RAG streaming error: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    # Terminal sentinel
    yield "data: [DONE]\n\n"
