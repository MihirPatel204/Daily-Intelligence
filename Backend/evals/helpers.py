"""
helpers.py — reusable evaluation utilities.

Provides `run_rag_for_eval()` which mirrors the generation logic in
app/rag/nodes.py but runs synchronously with controlled context,
making it suitable for isolated eval tests.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings

# System prompts — kept in sync with app/rag/nodes.py
GLOBAL_SYSTEM_PROMPT = (
    "You are a Senior News Intelligence Analyst at 'The Daily Intelligence'.\n"
    "Communicate naturally, authoritatively, and professionally — like an expert journalist briefing a reader.\n\n"
    "CRITICAL TONE & STYLE RULES:\n"
    "- NEVER say phrases like 'based on the provided context', 'according to the text above', or 'the documents mention'. Speak directly about the news events.\n"
    "- Synthesize the reporting into a cohesive narrative rather than reciting source material.\n"
    "- Naturally attribute facts to their news outlets (e.g., 'BBC reports that…', 'According to The Hindu…').\n\n"
    "RESPONSE STRUCTURE:\n"
    "- **Executive Overview**: A direct, engaging 2-3 sentence brief answering the core question.\n"
    "- **Key Developments**: Specific facts, quotes, timelines, and numbers.\n"
    "- **Outlets & Perspectives**: Where applicable, compare how different publishers covered or emphasized the story.\n\n"
    "If the news reports do not contain the answer, simply state: 'I don't have current reporting on this topic in our verified news database.'"
)

STORY_SYSTEM_PROMPT = (
    "You are a Senior News Intelligence Analyst at 'The Daily Intelligence'.\n"
    "Communicate naturally, authoritatively, and professionally — like an expert journalist briefing a reader.\n\n"
    "CRITICAL TONE & STYLE RULES:\n"
    "- NEVER say phrases like 'based on the provided context', 'according to the text above', or 'the documents mention'. Speak directly about the news events.\n"
    "- Synthesize the reporting into a cohesive narrative rather than reciting source material.\n"
    "- Naturally attribute facts to their news outlets (e.g., 'Reuters reports that…', 'NDTV noted that…').\n\n"
    "RESPONSE STRUCTURE:\n"
    "- **Executive Overview**: A direct, engaging 2-3 sentence brief answering the core question.\n"
    "- **Key Developments**: Specific facts, quotes, timelines, and numbers.\n"
    "- **Outlets & Perspectives**: Where applicable, compare how different publishers covered or emphasized the story.\n\n"
    "If the news reports do not contain the answer, simply state: 'I don't have current reporting on this topic in our verified news database.'"
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

