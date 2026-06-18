"""
Chat History Service — DB-backed persistence for conversation messages.

Replaces the in-memory MemorySaver with PostgreSQL storage so chat
history survives server restarts (PRD §7 chat_messages table).
"""

import logging
from typing import List, Optional

from app.db import get_db_connection, return_db_connection

logger = logging.getLogger(__name__)


def save_message(
    session_id: str,
    role: str,
    content: str,
    cluster_id: Optional[int] = None,
) -> None:
    """Persist a single chat message to the database."""
    conn = get_db_connection(register=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, cluster_id, role, content)
                VALUES (%s, %s, %s, %s);
                """,
                (session_id, cluster_id, role, content),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save chat message: {e}")
    finally:
        return_db_connection(conn)


def load_history(
    session_id: str,
    limit: int = 20,
) -> List[dict]:
    """
    Load recent chat messages for a session from the database.

    Returns a list of dicts: [{"role": "human"|"ai", "content": "..."}, ...]
    ordered oldest-first (ascending by created_at).
    """
    conn = get_db_connection(register=False)
    messages = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, created_at
                    FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                ) sub
                ORDER BY created_at ASC;
                """,
                (session_id, limit),
            )
            for role, content in cur.fetchall():
                messages.append({"role": role, "content": content})
    except Exception as e:
        logger.error(f"Failed to load chat history: {e}")
    finally:
        return_db_connection(conn)

    return messages


def clear_history(session_id: str) -> None:
    """Delete all messages for a session."""
    conn = get_db_connection(register=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE session_id = %s;",
                (session_id,),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to clear chat history: {e}")
    finally:
        return_db_connection(conn)
