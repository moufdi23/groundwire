"""
LangGraph agent: retrieve → generate → check_confidence → END.

Day 9: proves state flows correctly through a linear graph.
Tool-calling (create_ticket, check_status, escalate_to_human) is Day 10.

Public API
----------
app  — compiled LangGraph application.
       Usage: result = app.invoke({"question": "How do I enable RLS?"})

AgentState keys in the result dict:
  messages           — full conversation turn history (list of role/content dicts)
  question           — the original question
  retrieved_context  — top-3 reranked chunks (each has id, source_file, content, ...)
  answer             — Claude Haiku's generated answer
  needs_escalation   — True when the answer signals low confidence
"""

import operator
import sys
from pathlib import Path
from typing import Annotated, TypedDict

import anthropic
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from reranked_search import reranked_retrieve

# ── Anthropic client (lazy singleton) ─────────────────────────────────────────

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # Annotated with operator.add so each node that appends to messages uses
    # LangGraph's reducer (new list is concatenated, not replaced).
    messages: Annotated[list[dict], operator.add]
    question: str
    retrieved_context: list[dict]
    answer: str
    needs_escalation: bool


# ── Prompts & config ───────────────────────────────────────────────────────────

_MODEL = "claude-haiku-4-5"

_SYSTEM_PROMPT = (
    "You are a Supabase documentation assistant. "
    "Answer the user's question using ONLY the provided context passages. "
    "If the context does not contain enough information to answer the question, "
    'respond with exactly: "I don\'t have enough information to answer that." '
    "Do not rely on any knowledge outside the provided context."
)

_ESCALATION_PHRASES = (
    "i don't have enough information",
    "i'm not sure",
    "i am not sure",
    "cannot answer",
    "not enough information",
    "unable to answer",
)


# ── Node functions ─────────────────────────────────────────────────────────────

def retrieve(state: AgentState) -> dict:
    """Hybrid + cross-encoder retrieval; stores top-3 chunks in state."""
    chunks = reranked_retrieve(state["question"], k=3)
    return {"retrieved_context": chunks}


def generate(state: AgentState) -> dict:
    """Calls Claude Haiku with retrieved context; stores answer and appends to messages."""
    chunks = state["retrieved_context"]
    context_block = "\n\n---\n\n".join(
        f"[Source {i + 1}: {c['source_file']}]\n{c['content']}"
        for i, c in enumerate(chunks)
    )
    user_message = f"Context:\n{context_block}\n\nQuestion: {state['question']}"

    response = _get_client().messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    answer = next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )
    return {
        "answer": answer,
        "messages": [{"role": "assistant", "content": answer}],
    }


def check_confidence(state: AgentState) -> dict:
    """
    Rule-based confidence check: if the answer signals uncertainty,
    set needs_escalation=True so downstream routing (Day 10) can hand off.
    """
    answer_lower = state["answer"].lower()
    escalate = any(phrase in answer_lower for phrase in _ESCALATION_PHRASES)
    return {"needs_escalation": escalate}


# ── Graph ──────────────────────────────────────────────────────────────────────

_builder = StateGraph(AgentState)

_builder.add_node("retrieve", retrieve)
_builder.add_node("generate", generate)
_builder.add_node("check_confidence", check_confidence)

_builder.add_edge(START, "retrieve")
_builder.add_edge("retrieve", "generate")
_builder.add_edge("generate", "check_confidence")
_builder.add_edge("check_confidence", END)

app = _builder.compile()


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _TEST_CASES = [
        {
            "label": "Well-covered (confident answer expected)",
            "question": "What is Supabase?",
        },
        {
            "label": "Oddly specific (escalation expected)",
            "question": (
                "What is the default timeout in milliseconds for the GoTrue JWT "
                "validation middleware when running behind a Cloudflare Workers "
                "proxy with custom headers?"
            ),
        },
    ]

    print("Loading retrieval models (first run takes ~30 s) …\n")

    for case in _TEST_CASES:
        print("=" * 70)
        print(f"TEST : {case['label']}")
        print(f"Q    : {case['question']}")
        print("-" * 70)

        initial_state: AgentState = {
            "messages": [{"role": "user", "content": case["question"]}],
            "question": case["question"],
            "retrieved_context": [],
            "answer": "",
            "needs_escalation": False,
        }

        result = app.invoke(initial_state)

        top_source = (
            result["retrieved_context"][0]["source_file"]
            if result["retrieved_context"]
            else "none"
        )

        print(f"Answer:\n{result['answer']}")
        print()
        print(f"needs_escalation : {result['needs_escalation']}")
        print(f"Top source chunk : {top_source}")
        print(f"Messages in history: {len(result['messages'])}")
        print()
