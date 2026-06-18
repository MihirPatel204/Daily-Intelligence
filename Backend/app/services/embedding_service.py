"""
Embedding Service — wraps Google Gemini hosted embeddings via LangChain.

Provides a singleton GoogleGenerativeAIEmbeddings instance.
"""

import logging
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings

logger = logging.getLogger(__name__)

_embeddings_instance = None


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Return a singleton LangChain GoogleGenerativeAIEmbeddings instance."""
    global _embeddings_instance
    if _embeddings_instance is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}...")
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment.")
        _embeddings_instance = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.gemini_api_key,
        )
        logger.info("Embedding model loaded successfully.")
    return _embeddings_instance
