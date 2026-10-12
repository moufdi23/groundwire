# groundwire

![Retrieval Regression Gate](https://github.com/moufdi23/groundwire/actions/workflows/eval-gate.yml/badge.svg)

A production-grade AI support agent built with RAG, tool use, evaluations, and MCP — designed as a portfolio project demonstrating end-to-end LLM system design.

## Live Demo

Full stack RAG agent — try it live, no setup required.

- **App**: https://groundwire-4sqvljw4mrbiaadzxacrmd.streamlit.app
- **API docs**: https://web-production-29e6ca.up.railway.app/docs

## Current Status

**Backend API**: live on Railway (FastAPI)

**RAG pipeline**: hybrid search (vector + BM25) + cross-encoder reranking — recall@3 = 0.9125

**Agent**: LangGraph with 3 tools — `create_ticket`, `check_status`, `escalate_to_human`

**CI gate**: runs on every push; enforces recall@3 ≥ 0.88, recall@10 ≥ 0.95, precision@3 ≥ 0.75

**Known issue**: conversation memory (PostgresSaver) works locally but falls back to stateless on Railway due to a Supabase pooler connectivity issue — agent remains functional, history is not persisted between sessions

## What it does

Answers questions about Supabase documentation using a retrieval-augmented generation pipeline: documents are embedded, stored in Postgres with pgvector, and retrieved at query time to ground the agent's responses.

## Stack

- **Language**: Python 3.11
- **Vector store**: Supabase (Postgres + pgvector)
- **Embeddings**: sentence-transformers (local, no API cost)
- **Agent**: Claude (Anthropic)
- **Evals**: custom harness
- **Protocol**: MCP (Model Context Protocol)

## Project layout

```
src/         core library code (retrieval, agent, evals)
scripts/     one-off scripts (ingestion, connection tests)
data/        raw downloaded documents
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env         # then fill in your Supabase credentials
```

## Use it from Claude Desktop (MCP)

The MCP server exposes three tools that Claude Desktop can call directly:

| Tool | What it does |
|---|---|
| `search_knowledge_base` | Semantic + keyword search over the Supabase docs corpus |
| `create_ticket` | Opens a support ticket with a summary and priority level |
| `check_status` | Looks up the status of an existing ticket by ID |

**Setup**

1. Open Claude Desktop → **Settings → Developer → Edit Config**
2. Add the following block to `claude_desktop_config.json`, replacing every `YOUR_*` placeholder with your actual values:

```json
{
  "mcpServers": {
    "groundwire": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/absolute/path/to/groundwire",
      "env": {
        "SUPABASE_URL": "YOUR_SUPABASE_URL",
        "SUPABASE_KEY": "YOUR_SUPABASE_SERVICE_ROLE_KEY",
        "ANTHROPIC_API_KEY": "YOUR_ANTHROPIC_API_KEY"
      }
    }
  }
}
```

3. Restart Claude Desktop. You should see the three tools listed in the tool picker.

> **Note:** The first `search_knowledge_base` call in a session will be slow (5–15 s) while the embedding model loads into memory. Subsequent calls are fast.

## Day-by-day build log

- **Day 1**: Project scaffold, Supabase connection, corpus download
- **Day 2-3**: Embedding + chunking pipeline, pgvector ingestion
- **Day 4-5**: Retrieval layer + agent wiring
- **Day 6+**: Evals, MCP server, polish
