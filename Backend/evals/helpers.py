"""
helpers.py — reusable evaluation utilities.

Provides `run_rag_for_eval()` which mirrors the generation logic in
app/rag/nodes.py but runs synchronously with controlled context,
making it suitable for isolated eval tests.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings

# System prompts — kept in sync with app/rag/nodes.py L219-238
GLOBAL_SYSTEM_PROMPT = (
    "You are an AI News Intelligence Assistant for 'The Daily Intelligence'.\n"
    "Answer the user's question about recent news using ONLY the provided article context.\n"
    "For every claim, cite which publisher reported it "
    "(e.g., 'BBC reports…', 'According to India Today…').\n"
    "If the context doesn't contain enough information, state that clearly.\n"
    "Format your response in clean, readable markdown."
)

STORY_SYSTEM_PROMPT = (
    "You are an AI Editorial Assistant for 'The Daily Intelligence'.\n"
    "You are discussing a specific news story cluster. Ground your conversation "
    "ENTIRELY on the provided news reports.\n"
    "For every claim, cite which publisher reported it "
    "(e.g., 'According to NDTV…', 'Reuters reports…').\n"
    "If the question cannot be answered from the provided context, say so clearly.\n"
    "Format your response in clean, readable markdown."
)


def run_rag_for_eval(
    question: str,
    context_docs: list[str],
    story_scoped: bool = False,
) -> str:
    """
    Invoke the LLM with controlled context and return the response string.

    Parameters
    ----------
    question : str
        The user question to answer.
    context_docs : list[str]
        Pre-defined article snippets (the "retrieval context").
    story_scoped : bool
        If True, use the story-scoped system prompt; otherwise use the
        global news assistant prompt.

    Returns
    -------
    str
        The raw LLM response content.
    """
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.3,
    )

    system_prompt = STORY_SYSTEM_PROMPT if story_scoped else GLOBAL_SYSTEM_PROMPT
    context = "\n\n---\n\n".join(context_docs)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"News Articles Context:\n\n{context}\n\n"
                f"User Question: {question}"
            )
        ),
    ]

    response = llm.invoke(messages)
    from app.services.llm_service import clean_llm_content
    return clean_llm_content(response.content)

