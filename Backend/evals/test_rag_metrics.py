"""
test_rag_metrics.py — Core RAG quality evaluations.

Evaluates the LLM generation quality across 4 dimensions:
  1. Answer Relevancy  — Is the answer on-topic?
  2. Faithfulness       — Are claims backed by the retrieved articles?
  3. Contextual Relevancy — Did the retriever fetch useful articles?
  4. Hallucination      — Does the answer invent facts?

Each test is parametrized over the golden dataset so every test case
is evaluated independently and reported separately.

RUN:
    cd Backend
    deepeval test run evals/test_rag_metrics.py -v
"""

import json
import os

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric,
    HallucinationMetric,
)

from evals.helpers import run_rag_for_eval

# ---------------------------------------------------------------------------
# Load golden dataset
# ---------------------------------------------------------------------------

_DATASET_PATH = os.path.join(
    os.path.dirname(__file__), "datasets", "rag_golden.json"
)

with open(_DATASET_PATH) as _f:
    _ALL_CASES = json.load(_f)

# Only cases that have context (skip the "no-context-fallback" case)
CASES_WITH_CONTEXT = [c for c in _ALL_CASES if c["context"]]


def _case_id(case: dict) -> str:
    """Readable test-case ID for pytest output."""
    return case.get("id", case["input"][:50])


# ---------------------------------------------------------------------------
# Test 1: Answer Relevancy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES_WITH_CONTEXT, ids=[_case_id(c) for c in CASES_WITH_CONTEXT])
def test_answer_relevancy(case, gemini_judge):
    """
    Does the answer actually address the user's question?

    The judge extracts statements from the output and checks what fraction
    are relevant to the input.  Threshold 0.7 = at least 70% on-topic.
    """
    actual_output = run_rag_for_eval(case["input"], case["context"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=actual_output,
        retrieval_context=case["context"],
    )

    metric = AnswerRelevancyMetric(threshold=0.7, model=gemini_judge)
    assert_test(test_case, [metric])


# ---------------------------------------------------------------------------
# Test 2: Faithfulness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES_WITH_CONTEXT, ids=[_case_id(c) for c in CASES_WITH_CONTEXT])
def test_faithfulness(case, gemini_judge):
    """
    Is every claim in the answer supported by the provided articles?

    Particularly important for this project because the system prompt
    instructs the LLM to cite publishers. This metric catches fabricated
    attributions (e.g. 'BBC reports…' when BBC never said that).

    Threshold 0.8 = at least 80% of claims must be grounded.
    """
    actual_output = run_rag_for_eval(case["input"], case["context"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=actual_output,
        retrieval_context=case["context"],
    )

    metric = FaithfulnessMetric(threshold=0.8, model=gemini_judge)
    assert_test(test_case, [metric])


# ---------------------------------------------------------------------------
# Test 3: Contextual Relevancy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES_WITH_CONTEXT, ids=[_case_id(c) for c in CASES_WITH_CONTEXT])
def test_contextual_relevancy(case, gemini_judge):
    """
    Are the retrieved articles actually relevant to the user's question?

    This evaluates retrieval quality. In the golden dataset the context is
    hand-picked so scores should be high — if they're not, it means the
    metric setup is misconfigured.  For live retrieval tests, see
    test_e2e_pipeline.py.

    Threshold 0.7 = at least 70% of context docs are relevant.
    """
    actual_output = run_rag_for_eval(case["input"], case["context"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=actual_output,
        retrieval_context=case["context"],
    )

    metric = ContextualRelevancyMetric(threshold=0.7, model=gemini_judge)
    assert_test(test_case, [metric])


# ---------------------------------------------------------------------------
# Test 4: Hallucination
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES_WITH_CONTEXT, ids=[_case_id(c) for c in CASES_WITH_CONTEXT])
def test_hallucination(case, gemini_judge):
    """
    Does the answer contain information NOT present in the articles?

    Complementary to Faithfulness:
      - Faithfulness asks: "Are the stated claims supported?"
      - Hallucination asks: "Are there invented facts?"

    Threshold 0.7 = less than 30% hallucinated content.
    """
    actual_output = run_rag_for_eval(case["input"], case["context"])

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=actual_output,
        context=case["context"],  # HallucinationMetric uses `context`, not `retrieval_context`
    )

    metric = HallucinationMetric(threshold=0.7, model=gemini_judge)
    assert_test(test_case, [metric])

