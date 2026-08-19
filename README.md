# groundwire

A production-grade AI support agent built with RAG, tool use, evaluations, and MCP — designed as a portfolio project demonstrating end-to-end LLM system design.

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
