"""
Reranked retrieval: hybrid search candidates re-scored by a local cross-encoder.

Public API
----------
reranked_retrieve(query, k) -> list[dict]
    Returns the top-k chunks after cross-encoder reranking, each with:
    id, source_file, section, content, rerank_score.

Internals are lazily initialized on first call (cross-encoder model loads once).

Run standalone to smoke-test:
    python scripts/reranked_search.py
"""

import sys
from pathlib import Path

from sentence_transformers import CrossEncoder

# Ensure hybrid_search is importable when this script is run directly.
sys.path.insert(0, str(Path(__file__).parent))
from hybrid_search import hybrid_retrieve

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CANDIDATE_POOL = 50  # hybrid candidates fed to the cross-encoder

_cross_encoder = None


def _ensure_cross_encoder() -> None:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(RERANKER_MODEL)


def reranked_retrieve(query: str, k: int) -> list[dict]:
    """
    Retrieve top-k chunks using hybrid search + cross-encoder reranking.

    Steps:
      1. hybrid_retrieve(query, k=CANDIDATE_POOL) — broad candidate set
      2. CrossEncoder scores each (query, content) pair
      3. Re-sort by cross-encoder score, return top-k
    """
    _ensure_cross_encoder()

    candidates = hybrid_retrieve(query, k=CANDIDATE_POOL)

    pairs = [(query, c["content"]) for c in candidates]
    scores = _cross_encoder.predict(pairs)

    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    results = []
    for chunk, score in ranked[:k]:
        results.append({
            "id": chunk["id"],
            "source_file": chunk["source_file"],
            "section": chunk["section"],
            "content": chunk["content"],
            "rerank_score": float(score),
        })
    return results


if __name__ == "__main__":
    TEST_QUERY = "How do I enable row level security?"
    PREVIEW_CHARS = 300

    print(f'Running reranked_retrieve for: "{TEST_QUERY}"\n')
    top5 = reranked_retrieve(TEST_QUERY, k=5)

    print("=" * 60)
    for rank, r in enumerate(top5, 1):
        preview = r["content"][:PREVIEW_CHARS].replace("\n", " ")
        if len(r["content"]) > PREVIEW_CHARS:
            preview += " ..."
        print(
            f"[{rank}] id={r['id']}  rerank_score={r['rerank_score']:.4f}  "
            f"source={r['source_file']}"
        )
        print(f"     {preview}")
        print()
