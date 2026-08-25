"""
Build a BM25 index over all chunks in Supabase and save it to disk.

Pulls every (id, content) row from the `chunks` table, tokenises each chunk
with a simple lowercase-split tokeniser, builds a BM25Okapi index, then
pickles the index together with the ordered list of chunk IDs so we can map
scores back to rows at query time.

Output: data/bm25_index.pkl

Run: python scripts/build_bm25_index.py
"""

import os
import pickle
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
from supabase import create_client

load_dotenv()

OUTPUT_PATH = Path("data/bm25_index.pkl")
PAGE_SIZE = 1000


def tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def fetch_all_chunks(supabase) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            supabase.table("chunks")
            .select("id, content")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        batch = resp.data
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def main() -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")

    supabase = create_client(url, key)

    print("Fetching chunks from Supabase ...")
    chunks = fetch_all_chunks(supabase)
    if not chunks:
        sys.exit("No chunks found — have you run chunk_and_embed.py?")

    print(f"  {len(chunks)} chunks fetched")

    chunk_ids = [row["id"] for row in chunks]
    corpus = [tokenise(row["content"]) for row in chunks]

    print("Building BM25 index ...")
    bm25 = BM25Okapi(corpus)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": chunk_ids}, f)

    print(f"Index saved to {OUTPUT_PATH}")
    print(f"\nSummary: {len(chunks)} chunks indexed, {sum(len(t) for t in corpus)} total tokens")


if __name__ == "__main__":
    main()
