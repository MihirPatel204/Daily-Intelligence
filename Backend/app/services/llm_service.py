"""
LLM Service — wraps Google Gemini via LangChain.

Provides a singleton ChatGoogleGenerativeAI instance configured
from the application settings.
"""

import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings

logger = logging.getLogger(__name__)

_llm_instance = None


def get_llm() -> ChatGoogleGenerativeAI:
    """Return a singleton LangChain ChatGoogleGenerativeAI instance."""
    global _llm_instance
    if _llm_instance is None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment.")
        _llm_instance = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
            streaming=True,
        )
        logger.info(f"LLM initialized: {settings.gemini_model}")
    return _llm_instance


def clean_llm_content(content) -> str:
    """
    Extract a string representation of the content from an LLM chunk/message content.
    Handles content that may be a string, a list of dicts/strings, a dict, or other formats.
    """
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if "text" in part:
                    parts.append(part["text"])
                elif "content" in part:
                    parts.append(part["content"])
            elif hasattr(part, "text"):
                parts.append(part.text)
            elif hasattr(part, "content"):
                parts.append(part.content)
            else:
                parts.append(str(part))
        return "".join(parts)
    if isinstance(content, dict):
        if "text" in content:
            return content["text"]
        if "content" in content:
            return content["content"]
        return str(content)
    return str(content)

