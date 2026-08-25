"""
Smoke-test for the BM25 index.

Loads the pre-built index from data/bm25_index.pkl, scores the hardcoded
test query against it, fetches metadata for the top-K chunk IDs from
Supabase, and prints the results.

Run: python scripts/test_bm25.py
Prerequisite: run build_bm25_index.py first.
"""

import os
import pickle
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

INDEX_PATH = Path("data/bm25_index.pkl")
TEST_QUERY = "How do I enable row level security?"
TOP_K = 5
PREVIEW_CHARS = 300


def tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def main() -> None:
    if not INDEX_PATH.exists():
        sys.exit(f"Index not found at {INDEX_PATH}. Run build_bm25_index.py first.")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")

    supabase = create_client(url, key)

    print(f"Loading BM25 index from {INDEX_PATH} ...")
    with open(INDEX_PATH, "rb") as f:
        payload = pickle.load(f)

    bm25 = payload["bm25"]
    chunk_ids: list = payload["chunk_ids"]

    print(f'Scoring query: "{TEST_QUERY}"\n')
    tokens = tokenise(TEST_QUERY)
    scores = bm25.get_scores(tokens)

    # Pair each chunk_id with its score and sort descending
    ranked = sorted(zip(chunk_ids, scores), key=lambda x: x[1], reverse=True)
    top_ids = [cid for cid, _ in ranked[:TOP_K]]
    top_scores = {cid: score for cid, score in ranked[:TOP_K]}

    # Fetch metadata for the top chunks in one round-trip
    resp = (
        supabase.table("chunks")
        .select("id, source_file, content")
        .in_("id", top_ids)
        .execute()
    )
    rows_by_id = {row["id"]: row for row in resp.data}

    print(f"{'='*60}")
    for rank, cid in enumerate(top_ids, 1):
        row = rows_by_id.get(cid, {})
        score = top_scores[cid]
        source = row.get("source_file", "unknown")
        content = row.get("content", "")
        preview = content[:PREVIEW_CHARS].replace("\n", " ")
        if len(content) > PREVIEW_CHARS:
            preview += " ..."

        print(f"[{rank}] id={cid}  bm25_score={score:.4f}  source={source}")
        print(f"     {preview}")
        print()


if __name__ == "__main__":
    main()
