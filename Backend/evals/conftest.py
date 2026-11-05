"""
conftest.py — shared setup for all DeepEval tests.

This file runs automatically before any test in the evals/ directory.
It configures:
  1. The "judge" LLM that DeepEval uses to score outputs (Gemini).
  2. sys.path so that `app.*` imports work from the evals/ folder.
"""

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Make Backend/app importable from the evals/ directory
# ---------------------------------------------------------------------------
_backend_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv

load_dotenv(os.path.join(_backend_dir, ".env"))

# ---------------------------------------------------------------------------
# Gemini-based judge LLM
# ---------------------------------------------------------------------------
from deepeval.models import DeepEvalBaseLLM
from langchain_google_genai import ChatGoogleGenerativeAI


class GeminiJudge(DeepEvalBaseLLM):
    """
    Custom wrapper so DeepEval uses your existing Gemini API key as the
    evaluation judge instead of defaulting to OpenAI.

    - temperature=0  → deterministic, reproducible scores
    - gemini-3.8-flash → capable enough to judge faithfulness / relevancy
    """

    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0,
        )

    def load_model(self):
        return self.model

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.model.invoke(prompt)
        from app.services.llm_service import clean_llm_content
        return clean_llm_content(response.content)

    async def a_generate(self, prompt: str, **kwargs) -> str:
        response = await self.model.ainvoke(prompt)
        from app.services.llm_service import clean_llm_content
        return clean_llm_content(response.content)

    def get_model_name(self) -> str:
        return "gemini-3.5-flash-lite"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def gemini_judge():
    """Session-scoped Gemini judge — shared across all tests to avoid
    re-instantiating the LLM on every test case."""
    return GeminiJudge()

