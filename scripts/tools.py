"""
Agent tools backed by Supabase.

    create_ticket(question, answer)           -> dict  — logs a resolved Q&A (status='auto_resolved')
    check_status(ticket_id)                   -> dict  — looks up a ticket by id
    escalate_to_human(question, answer, reason) -> dict — logs a low-confidence Q&A (status='escalated')

All three functions return the full ticket row on success, or a plain dict with
an 'error' key on failure so the agent can include the message in its response.
"""

import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_TABLE = "tickets"

# ── Lazy Supabase client ───────────────────────────────────────────────────────

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env")
        _client = create_client(url, key)
    return _client


# ── Tools ──────────────────────────────────────────────────────────────────────

def create_ticket(question: str, answer: str) -> dict:
    """Insert a resolved Q&A into the tickets table (status='auto_resolved')."""
    try:
        row = (
            _get_client()
            .table(_TABLE)
            .insert({"question": question, "answer": answer, "status": "auto_resolved"})
            .execute()
        )
        return row.data[0] if row.data else {"error": "insert returned no data"}
    except Exception as exc:
        return {"error": str(exc)}


def check_status(ticket_id: int) -> dict:
    """Return a ticket's current status and details, or a not-found message."""
    try:
        row = (
            _get_client()
            .table(_TABLE)
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not row.data:
            return {"found": False, "message": f"No ticket with id={ticket_id}"}
        record = row.data[0]
        return {"found": True, **record}
    except Exception as exc:
        return {"error": str(exc)}


def escalate_to_human(question: str, answer: str, reason: str) -> dict:
    """Insert a low-confidence Q&A into the tickets table (status='escalated')."""
    try:
        row = (
            _get_client()
            .table(_TABLE)
            .insert({
                "question": question,
                "answer": answer,
                "reason": reason,
                "status": "escalated",
            })
            .execute()
        )
        return row.data[0] if row.data else {"error": "insert returned no data"}
    except Exception as exc:
        return {"error": str(exc)}
