import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import agent as _agent_module
from agent import _make_state
from agent import app as agent_graph

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open the Postgres connection pool and initialise the checkpointer table
    # here, after the process is fully up, so cold-start latency doesn't cause
    # the pool to time out before any connections are ever attempted.
    pool = _agent_module._pool
    checkpointer = _agent_module._checkpointer
    if pool is not None:
        try:
            pool.open(wait=True, timeout=15)
            _log.info("Connection pool opened.")
            if checkpointer is not None:
                checkpointer.setup()
                _log.info("PostgresSaver checkpointer ready.")
        except Exception as exc:
            _log.warning("Pool/checkpointer startup failed (%s); running without memory.", exc)
    yield
    if pool is not None:
        try:
            pool.close()
        except Exception:
            pass


app = FastAPI(title="groundwire", lifespan=lifespan)


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
