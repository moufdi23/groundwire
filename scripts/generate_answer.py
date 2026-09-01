"""
Answer generation: retrieves top-k reranked chunks and calls Claude Haiku 4.5
to produce a grounded answer.

Public API
----------
generate_answer(question, k=3) -> tuple[str, list[str]]
    Returns (answer_text, context_contents).
    answer_text       — Claude's response, grounded strictly to the retrieved context.
    context_contents  — list of raw chunk text strings used as context.

Run standalone to smoke-test:
    python scripts/generate_answer.py
"""

import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from reranked_search import reranked_retrieve

MODEL = "claude-haiku-4-5"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


SYSTEM_PROMPT = (
    "You are a Supabase documentation assistant. "
    "Answer the user's question using ONLY the provided context passages. "
    "If the context does not contain enough information to answer the question, "
    'respond with exactly: "I don\'t have enough information to answer that." '
    "Do not rely on any knowledge outside the provided context."
)


def generate_answer(question: str, k: int = 3) -> tuple[str, list[str]]:
    """
    Retrieve top-k reranked chunks and generate a grounded answer via Claude Haiku.

    Returns:
        (answer, contexts)
        answer   — Claude's generated text response
        contexts — list of chunk text strings used as context (same order as retrieved)
    """
    chunks = reranked_retrieve(question, k=k)
    contexts = [c["content"] for c in chunks]

    context_block = "\n\n---\n\n".join(
        f"[Source {i + 1}: {chunks[i]['source_file']}]\n{text}"
        for i, text in enumerate(contexts)
    )

    user_message = f"""Context:
{context_block}

Question: {question}"""

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    answer = next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )
    return answer, contexts


if __name__ == "__main__":
    TEST_QUERY = "How do I enable row level security?"

    print(f'Test query: "{TEST_QUERY}"\n')
    print("Loading retrieval models (first run takes ~30s) ...")
    answer, contexts = generate_answer(TEST_QUERY, k=3)

    print()
    print("=" * 60)
    print("Generated Answer")
    print("=" * 60)
    print(answer)
    print()
    print("=" * 60)
    print("Source Chunks Used")
    print("=" * 60)
    for i, ctx in enumerate(contexts, 1):
        preview = ctx[:300].replace("\n", " ")
        if len(ctx) > 300:
            preview += " ..."
        print(f"[{i}] {preview}")
        print()
