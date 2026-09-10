"""
LangGraph agent: classify_intent → (lookup_status | retrieve → generate → check_confidence → resolve | handle_escalation) → END.

Day 11: adds intent classification for status checks, retry logic with exponential backoff,
        output validation, and a tool-call safety counter.

Public API
----------
app  — compiled LangGraph application.
       Usage: result = app.invoke({"question": "What is Supabase?"})
              result = app.invoke({"question": "What's the status of ticket 1?"})

AgentState keys in the result dict:
  messages           — full conversation turn history (list of role/content dicts)
  question           — the original question
  retrieved_context  — top-3 reranked chunks (normal Q&A path only)
  answer             — generated or looked-up answer
  needs_escalation   — True when the answer signals low confidence (normal path only)
  ticket             — the ticket row returned from Supabase
  tool_calls         — cumulative count of Supabase tool invocations in this run
  path_taken         — "normal" | "status_lookup"
  ticket_id_to_lookup — extracted ticket id (status_lookup path only, else None)
"""

import logging
import operator
import re
import sys
import time
from pathlib import Path
from typing import Annotated, TypedDict

import anthropic
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from reranked_search import reranked_retrieve
from tools import check_status, create_ticket, escalate_to_human

_log = logging.getLogger(__name__)

# ── Anthropic client (lazy singleton) ─────────────────────────────────────────

_anthropic: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.Anthropic()
    return _anthropic


# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    question: str
    retrieved_context: list[dict]
    answer: str
    needs_escalation: bool
    ticket: dict
    tool_calls: Annotated[int, operator.add]    # accumulates; LangGraph adds each node's return value
    path_taken: str                              # "normal" | "status_lookup"
    ticket_id_to_lookup: int | None


# ── Config ─────────────────────────────────────────────────────────────────────

_MODEL = "claude-haiku-4-5"
_MAX_TOOL_CALLS = 1          # safety guard: warn if a single run exceeds this
_MIN_ANSWER_LEN = 10         # answers shorter than this are treated as low-confidence

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

# Matches "ticket 123", "ticket #123", "status of ticket 123", etc.
_TICKET_ID_RE = re.compile(r"ticket\s*#?\s*(\d+)", re.IGNORECASE)

# Delays (seconds) before retry attempts 2 and 3; no delay before attempt 1 or after the final attempt.
_RETRY_DELAYS = (1, 2)


# ── Node functions ─────────────────────────────────────────────────────────────

def classify_intent(state: AgentState) -> dict:
    """Detect whether the question is a ticket status check; extract the ticket id if so."""
    match = _TICKET_ID_RE.search(state["question"])
    if match:
        ticket_id = int(match.group(1))
        _log.info("Intent: status_lookup (ticket_id=%d)", ticket_id)
        return {"path_taken": "status_lookup", "ticket_id_to_lookup": ticket_id}
    _log.info("Intent: normal Q&A")
    return {"path_taken": "normal", "ticket_id_to_lookup": None}


def lookup_status(state: AgentState) -> dict:
    """Call check_status() and return a human-readable answer; skips retrieval/generation."""
    current = state.get("tool_calls", 0)
    if current >= _MAX_TOOL_CALLS:
        _log.warning("Safety limit: tool_calls already at %d before lookup_status", current)

    ticket_id = state["ticket_id_to_lookup"]
    result = check_status(ticket_id)

    if result.get("found"):
        answer = (
            f"Ticket #{ticket_id} — status: {result.get('status', 'N/A')}. "
            f"Original question: {result.get('question', '')}. "
            f"Answer on file: {result.get('answer', 'none')}."
        )
    else:
        answer = result.get("message", f"No ticket with id={ticket_id}.")

    return {
        "ticket": result,
        "answer": answer,
        "tool_calls": 1,
        "messages": [{"role": "assistant", "content": answer}],
    }


def retrieve(state: AgentState) -> dict:
    chunks = reranked_retrieve(state["question"], k=3)
    return {"retrieved_context": chunks}


def generate(state: AgentState) -> dict:
    """Call Claude with retry logic (3 attempts, 1s/2s exponential backoff)."""
    chunks = state["retrieved_context"]
    context_block = "\n\n---\n\n".join(
        f"[Source {i + 1}: {c['source_file']}]\n{c['content']}"
        for i, c in enumerate(chunks)
    )
    user_message = f"Context:\n{context_block}\n\nQuestion: {state['question']}"

    last_exc: Exception | None = None
    answer = ""
    max_attempts = len(_RETRY_DELAYS) + 1   # 3

    for attempt in range(1, max_attempts + 1):
        try:
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
            break
        except Exception as exc:
            last_exc = exc
            _log.warning("generate attempt %d/%d failed: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                delay = _RETRY_DELAYS[attempt - 1]
                _log.info("Retrying in %ds…", delay)
                time.sleep(delay)
    else:
        raise RuntimeError(
            f"All {max_attempts} generate attempts failed. Last error: {last_exc}"
        ) from last_exc

    return {
        "answer": answer,
        "messages": [{"role": "assistant", "content": answer}],
    }


def check_confidence(state: AgentState) -> dict:
    """Output validation + phrase heuristic; forces escalation if answer is invalid."""
    answer = state["answer"]
    escalate = len(answer.strip()) < _MIN_ANSWER_LEN or any(
        phrase in answer.lower() for phrase in _ESCALATION_PHRASES
    )
    return {"needs_escalation": escalate}


def resolve(state: AgentState) -> dict:
    """Confident answer: log to Supabase as auto_resolved."""
    current = state.get("tool_calls", 0)
    if current >= _MAX_TOOL_CALLS:
        _log.warning("Safety limit: tool_calls already at %d before resolve", current)
    ticket = create_ticket(state["question"], state["answer"])
    return {"ticket": ticket, "tool_calls": 1}


def handle_escalation(state: AgentState) -> dict:
    """Low-confidence answer: escalate to human queue in Supabase."""
    current = state.get("tool_calls", 0)
    if current >= _MAX_TOOL_CALLS:
        _log.warning("Safety limit: tool_calls already at %d before handle_escalation", current)
    ticket = escalate_to_human(
        state["question"],
        state["answer"],
        reason="low confidence answer",
    )
    return {"ticket": ticket, "tool_calls": 1}


# ── Routing ────────────────────────────────────────────────────────────────────

def _route_after_classify(state: AgentState) -> str:
    return "lookup_status" if state.get("path_taken") == "status_lookup" else "retrieve"


def _route_after_confidence(state: AgentState) -> str:
    return "handle_escalation" if state["needs_escalation"] else "resolve"


# ── Graph ──────────────────────────────────────────────────────────────────────

_builder = StateGraph(AgentState)

_builder.add_node("classify_intent", classify_intent)
_builder.add_node("lookup_status", lookup_status)
_builder.add_node("retrieve", retrieve)
_builder.add_node("generate", generate)
_builder.add_node("check_confidence", check_confidence)
_builder.add_node("resolve", resolve)
_builder.add_node("handle_escalation", handle_escalation)

_builder.add_edge(START, "classify_intent")
_builder.add_conditional_edges(
    "classify_intent",
    _route_after_classify,
    {"lookup_status": "lookup_status", "retrieve": "retrieve"},
)
_builder.add_edge("lookup_status", END)
_builder.add_edge("retrieve", "generate")
_builder.add_edge("generate", "check_confidence")
_builder.add_conditional_edges(
    "check_confidence",
    _route_after_confidence,
    {"resolve": "resolve", "handle_escalation": "handle_escalation"},
)
_builder.add_edge("resolve", END)
_builder.add_edge("handle_escalation", END)

app = _builder.compile()


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    _TEST_CASES = [
        {
            "label": "Well-covered (confident answer expected → auto_resolved)",
            "question": "What is Supabase?",
        },
        {
            "label": "Oddly specific (escalation expected → escalated)",
            "question": (
                "What is the default timeout in milliseconds for the GoTrue JWT "
                "validation middleware when running behind a Cloudflare Workers "
                "proxy with custom headers?"
            ),
        },
        {
            "label": "Status lookup (direct ticket check → lookup_status path)",
            "question": "What's the status of ticket 1?",
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
            "ticket": {},
            "tool_calls": 0,
            "path_taken": "",
            "ticket_id_to_lookup": None,
        }

        result = app.invoke(initial_state)

        path = result.get("path_taken", "")
        ticket = result.get("ticket", {})
        ticket_id = ticket.get("id", "N/A")
        ticket_status = ticket.get("status", "N/A")

        if path == "status_lookup":
            display_path = "STATUS-LOOKUP"
        elif result["needs_escalation"]:
            display_path = "ESCALATED"
        else:
            display_path = "AUTO-RESOLVED"

        print(f"Path taken       : {display_path}")
        print(f"Answer:\n{result['answer']}")
        print()
        print(f"needs_escalation : {result['needs_escalation']}")
        print(f"Ticket id        : {ticket_id}")
        print(f"Ticket status    : {ticket_status}")
        print(f"Tool calls       : {result.get('tool_calls', 0)}")

        if path != "status_lookup":
            top_source = (
                result["retrieved_context"][0]["source_file"]
                if result["retrieved_context"]
                else "none"
            )
            print(f"Top source chunk : {top_source}")

        if path == "status_lookup":
            found = ticket.get("found")
            print(f"Ticket found     : {found}")
            if found:
                print(f"Ticket question  : {ticket.get('question', '')}")

        print(f"Messages in history: {len(result['messages'])}")
        if ticket.get("error"):
            print(f"[WARN] Ticket error: {ticket['error']}")
        print()
