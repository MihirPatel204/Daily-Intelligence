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
