# groundwire

![Retrieval Regression Gate](https://github.com/moufdi23/groundwire/actions/workflows/eval-gate.yml/badge.svg)

A production-grade AI support agent built with RAG, tool use, evaluations, and MCP — designed as a portfolio project demonstrating end-to-end LLM system design.

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

## Day-by-day build log

- **Day 1**: Project scaffold, Supabase connection, corpus download
- **Day 2-3**: Embedding + chunking pipeline, pgvector ingestion
- **Day 4-5**: Retrieval layer + agent wiring
- **Day 6+**: Evals, MCP server, polish
