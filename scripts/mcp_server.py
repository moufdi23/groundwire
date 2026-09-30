"""
MCP server exposing groundwire knowledge-base search and ticket tools.

Run (stdio transport, for Claude Desktop / MCP Inspector):
    python scripts/mcp_server.py

The server registers three tools:
    search_knowledge_base  — reranked hybrid RAG retrieval
    create_ticket          — log a resolved Q&A to Supabase
    check_status           — look up a ticket by id
"""

import sys
from pathlib import Path

# Make sibling scripts importable when run from any working directory.
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer

from reranked_search import reranked_retrieve
from tools import create_ticket as _create_ticket, check_status as _check_status

mcp = MCPServer("groundwire")

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
    raw = reranked_retrieve(query, k=k)
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
def create_ticket(question: str, answer: str) -> dict:
    """
    Log a resolved Q&A pair as a support ticket in the groundwire Supabase database.

    Creates a ticket with status='auto_resolved' and returns the full ticket row,
    including the auto-assigned ticket id.

    Use this tool after successfully answering a user's support question, so the
    interaction is recorded for audit or follow-up.

    Args:
        question: The user's original question.
        answer: The answer that was provided.
    """
    return _create_ticket(question, answer)


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
