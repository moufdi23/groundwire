"""
Hybrid retrieval: vector search + BM25 fused with Reciprocal Rank Fusion (RRF).

Public API
----------
hybrid_retrieve(query, k) -> list[dict]
    Returns the top-k fused chunks, each with:
    id, source_file, section, content, fused_score.

Internals are lazily initialized on first call (Supabase client, embedding
model, BM25 index), so importing this module is cheap.

Run standalone to smoke-test:
    python scripts/hybrid_search.py
"""

import os
import pickle
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client

load_dotenv()

INDEX_PATH = Path("data/bm25_index.pkl")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_POOL = 50   # candidates fetched from vector search before fusion
BM25_POOL = 50     # candidates fetched from BM25 before fusion
RRF_K = 60         # RRF denominator constant

_supabase_client = None
_bm25 = None
_chunk_ids: list | None = None
_model = None


def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _ensure_initialized() -> None:
    global _supabase_client, _bm25, _chunk_ids, _model

    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            sys.exit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")
        _supabase_client = create_client(url, key)

    if _bm25 is None:
        if not INDEX_PATH.exists():
            sys.exit(f"BM25 index not found at {INDEX_PATH}. Run build_bm25_index.py first.")
        with open(INDEX_PATH, "rb") as f:
            payload = pickle.load(f)
        _bm25 = payload["bm25"]
        _chunk_ids = payload["chunk_ids"]

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)


def hybrid_retrieve(query: str, k: int) -> list[dict]:
    """
    Fuse vector search and BM25 via Reciprocal Rank Fusion.

    score(chunk) = sum of 1 / (RRF_K + rank) across whichever lists contain it.
    Ranks start at 1; RRF_K=60 (standard default).
    """
    _ensure_initialized()

    # ── 1. Vector search ─────────────────────────────────────────────────────
    query_vec: list[float] = _model.encode(query, convert_to_numpy=True).tolist()
    resp = _supabase_client.rpc(
        "match_chunks",
        {"query_embedding": query_vec, "match_count": VECTOR_POOL},
    ).execute()
    vector_results = resp.data or []

    vector_rank: dict[int, int] = {}
    meta_cache: dict[int, dict] = {}
    for rank, row in enumerate(vector_results, 1):
        cid = row["id"]
        vector_rank[cid] = rank
        meta_cache[cid] = {
            "id": cid,
            "source_file": row.get("source_file", ""),
            "section": row.get("section", ""),
            "content": row.get("content", ""),
        }

    # ── 2. BM25 search ───────────────────────────────────────────────────────
    tokens = _tokenise(query)
    bm25_scores = _bm25.get_scores(tokens)
    ranked_bm25 = sorted(
        zip(_chunk_ids, bm25_scores), key=lambda x: x[1], reverse=True
    )[:BM25_POOL]

    bm25_rank: dict[int, int] = {}
    for rank, (cid, _) in enumerate(ranked_bm25, 1):
        bm25_rank[cid] = rank

    # ── 3. Reciprocal Rank Fusion ─────────────────────────────────────────────
    all_ids = set(vector_rank) | set(bm25_rank)
    fused: list[tuple[int, float]] = []
    for cid in all_ids:
        score = 0.0
        if cid in vector_rank:
            score += 1.0 / (RRF_K + vector_rank[cid])
        if cid in bm25_rank:
            score += 1.0 / (RRF_K + bm25_rank[cid])
        fused.append((cid, score))

    fused.sort(key=lambda x: x[1], reverse=True)
    top_k = fused[:k]

    # ── 4. Fetch metadata only for BM25-only chunks that made the top-k ───────
    missing_ids = [cid for cid, _ in top_k if cid not in meta_cache]
    if missing_ids:
        resp2 = (
            _supabase_client.table("chunks")
            .select("id, source_file, section, content")
            .in_("id", missing_ids)
            .execute()
        )
        for row in resp2.data:
            cid = row["id"]
            meta_cache[cid] = {
                "id": cid,
                "source_file": row.get("source_file", ""),
                "section": row.get("section", ""),
                "content": row.get("content", ""),
            }

    results = []
    for cid, score in top_k:
        meta = meta_cache.get(cid, {})
        results.append({
            "id": cid,
            "source_file": meta.get("source_file", ""),
            "section": meta.get("section", ""),
            "content": meta.get("content", ""),
            "fused_score": score,
        })

    return results


if __name__ == "__main__":
    TEST_QUERY = "How do I enable row level security?"
    PREVIEW_CHARS = 300

    print(f'Running hybrid_retrieve for: "{TEST_QUERY}"\n')
    top5 = hybrid_retrieve(TEST_QUERY, k=5)

    print("=" * 60)
    for rank, r in enumerate(top5, 1):
        preview = r["content"][:PREVIEW_CHARS].replace("\n", " ")
        if len(r["content"]) > PREVIEW_CHARS:
            preview += " ..."
        print(
            f"[{rank}] id={r['id']}  fused_score={r['fused_score']:.6f}  "
            f"source={r['source_file']}"
        )
        print(f"     {preview}")
        print()
