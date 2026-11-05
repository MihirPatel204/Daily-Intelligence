"""
test_e2e_pipeline.py — End-to-end RAG pipeline evaluations.

Unlike test_rag_metrics.py (which uses hardcoded context to test
generation in isolation), these tests call the REAL retrieve → grade →
generate chain against your database.

REQUIRES: A running PostgreSQL database with ingested articles.

RUN:
    cd Backend
    deepeval test run evals/test_e2e_pipeline.py -v
"""

import asyncio

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric

from app.rag.nodes import retrieve_node, grade_node, generate_node

# ---------------------------------------------------------------------------
# Sample questions for E2E testing
# ---------------------------------------------------------------------------

E2E_QUESTIONS = [
    "What were the key results and reactions from the US midterm elections?",
    "What did the UN Human Rights Commissioner say about Kerala and poverty?",
    "Why are conservationists concerned about the Malshahi Masjid restoration?",
]


def _run_pipeline(question: str) -> tuple[str, list[str]]:
    """
    Execute the full RAG pipeline synchronously and return
    (generation_text, list_of_context_strings).
    """
    state = {
        "question": question,
        "cluster_id": None,
        "documents": [],
        "messages": [],
        "generation": "",
        "citations": [],
    }

    # Step 1: Retrieve
    state.update(retrieve_node(state))

    # Step 2: Grade / filter
    state.update(grade_node(state))

    if not state["documents"]:
        return "", []

    # Step 3: Generate (async node — run in sync wrapper)
    result = asyncio.run(generate_node(state))

    # Build context strings from the retrieved docs
    retrieval_context = [
        f"{d['source_name']}: {d['title']}\n"
        f"{d.get('raw_text', d.get('summary', ''))[:500]}"
        for d in state["documents"]
    ]

    return result.get("generation", ""), retrieval_context


# ---------------------------------------------------------------------------
# Test: E2E Faithfulness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", E2E_QUESTIONS)
def test_e2e_faithfulness(question, gemini_judge):
    """
    Full pipeline faithfulness: Are the claims in the final answer backed
    by the articles that were actually retrieved from the database?
    """
    generation, retrieval_context = _run_pipeline(question)

    if not generation:
        pytest.skip(f"No documents retrieved for: {question}")

    test_case = LLMTestCase(
        input=question,
        actual_output=generation,
        retrieval_context=retrieval_context,
    )

    metric = FaithfulnessMetric(threshold=0.7, model=gemini_judge)
    assert_test(test_case, [metric])


# ---------------------------------------------------------------------------
# Test: E2E Answer Relevancy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", E2E_QUESTIONS)
def test_e2e_answer_relevancy(question, gemini_judge):
    """
    Full pipeline relevancy: Does the final answer actually address
    the user's question?
    """
    generation, retrieval_context = _run_pipeline(question)

    if not generation:
        pytest.skip(f"No documents retrieved for: {question}")

    test_case = LLMTestCase(
        input=question,
        actual_output=generation,
        retrieval_context=retrieval_context,
    )

    metric = AnswerRelevancyMetric(threshold=0.7, model=gemini_judge)
    assert_test(test_case, [metric])

