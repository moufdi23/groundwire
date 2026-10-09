"""
MCP server exposing groundwire knowledge-base search and ticket tools.

Run (stdio transport, for Claude Desktop / MCP Inspector):
    python scripts/mcp_server.py

The server registers three tools:
    search_knowledge_base  — reranked hybrid RAG retrieval
    create_ticket          — log a resolved Q&A to Supabase
    check_status           — look up a ticket by id
"""

import logging
import sys
from pathlib import Path

# MCP uses stdio for JSON-RPC; any incidental output must go to stderr.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

# Make sibling scripts importable when run from any working directory.
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer
from tools import (
    create_ticket as _create_ticket,
    check_status as _check_status,
    escalate_to_human as _escalate_to_human,
)

mcp = MCPServer("groundwire")

# Lazy handle — populated on first search_knowledge_base call.
_reranked_retrieve = None

CONTENT_PREVIEW = 500  # characters shown per chunk to keep payloads readable


@mcp.tool()
def search_knowledge_base(query: str, k: int = 3) -> list[dict]:
    """
    Search the groundwire knowledge base using hybrid retrieval + cross-encoder reranking.

    Returns the top-k most relevant chunks.  Each result contains:
      - source_file: the documentation file the chunk came from
      - section: the section heading (may be empty)
      - preview: first 500 characters of the chunk text
      - rerank_score: cross-encoder relevance score (higher = more relevant)

    Use this tool whenever the user asks a question that requires looking up
    Supabase documentation, product features, or groundwire knowledge-base content.

    Args:
        query: Natural-language question or search phrase.
        k: Number of results to return (default 3, max recommended 10).
    """
    global _reranked_retrieve
    if _reranked_retrieve is None:
        from reranked_search import reranked_retrieve  # noqa: PLC0415
        _reranked_retrieve = reranked_retrieve
    raw = _reranked_retrieve(query, k=k)
    return [
        {
            "source_file": r["source_file"],
            "section": r.get("section", ""),
            "preview": r["content"][:CONTENT_PREVIEW],
            "rerank_score": r["rerank_score"],
        }
        for r in raw
    ]


@mcp.tool()
def create_ticket(
    question: str,
    answer: str,
    resolved: bool = False,
    reason: str = "",
) -> dict:
    """
    Log a support interaction as a ticket in the groundwire Supabase database.

    By default (resolved=False) the ticket is created with status='escalated' so a
    human agent will review it.  Set resolved=True only when you are confident the
    answer fully solves the user's problem; the ticket is then stored as
    status='auto_resolved'.

    When to use each value:
      resolved=False (default) — use whenever the answer may be incomplete, the user
        expressed doubt, the question was outside the knowledge base, or you are unsure.
        Optionally supply a reason so the human reviewer understands why it was flagged.
      resolved=True — use only after a clear, complete answer was confirmed by the user.

    Returns the full ticket row including the auto-assigned ticket id.

    Args:
        question: The user's original question.
        answer: The answer that was provided.
        resolved: False (default) creates an escalated ticket; True marks it auto_resolved.
        reason: Optional human-readable explanation for escalation (ignored when resolved=True).
    """
    if resolved:
        return _create_ticket(question, answer)
    return _escalate_to_human(question, answer, reason or "Flagged for human review")


@mcp.tool()
def check_status(ticket_id: int) -> dict:
    """
    Look up a support ticket by its numeric id.

    Returns the full ticket row (id, question, answer, status, created_at, …) when
    found, or {"found": false, "message": "..."} when no ticket exists with that id.

    Use this tool when a user asks about the status or details of a previously
    created ticket.

    Args:
        ticket_id: The integer id returned when the ticket was created.
    """
    return _check_status(ticket_id)


if __name__ == "__main__":
    mcp.run()
