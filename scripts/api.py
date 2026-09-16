import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import _make_state
from agent import app as agent_graph

app = FastAPI(title="groundwire")


# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    needs_escalation: bool
    path_taken: str
    ticket_id: int | None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "groundwire API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    state = _make_state(request.message)
    config = {"configurable": {"thread_id": request.thread_id}}
    try:
        result = agent_graph.invoke(state, config=config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    ticket = result.get("ticket") or {}
    return ChatResponse(
        answer=result["answer"],
        thread_id=request.thread_id,
        needs_escalation=result.get("needs_escalation", False),
        path_taken=result.get("path_taken", ""),
        ticket_id=ticket.get("id"),
    )
