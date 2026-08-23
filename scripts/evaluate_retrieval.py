"""
Baseline retrieval evaluation against the golden set.

Loads data/golden_set.jsonl (80 entries), embeds each question with the same
local model used during ingestion, queries Supabase via match_chunks, and
computes recall@k and precision@k for k ∈ {3, 5, 10}.

Recall@k   — was the source_chunk_id present in the top-k results?
Precision@k — fraction of top-k results from the same section as the source chunk
              (section-match is used as a relevance proxy).

Writes RESULTS.md to the project root and prints the table to stdout.

Run: python scripts/evaluate_retrieval.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client

load_dotenv()

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
GOLDEN_SET_PATH = Path("data/golden_set.jsonl")
KS = [3, 5, 10]
MAX_K = max(KS)


def load_golden_set(path: Path) -> list[dict]:
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def fetch_source_sections(supabase, chunk_ids: list[int]) -> dict[int, str]:
    """Return {chunk_id: section} for a list of chunk ids."""
    response = (
        supabase.table("chunks")
        .select("id, section")
        .in_("id", chunk_ids)
        .execute()
    )
    return {row["id"]: row.get("section", "") for row in response.data}


def main() -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")

    if not GOLDEN_SET_PATH.exists():
        sys.exit(f"Golden set not found at {GOLDEN_SET_PATH}")

    supabase = create_client(url, key)

    print("Loading golden set ...")
    entries = load_golden_set(GOLDEN_SET_PATH)
    total = len(entries)
    print(f"  {total} entries loaded.")

    # Pre-fetch section metadata for all source chunks in one query.
    source_ids = [e["source_chunk_id"] for e in entries]
    print("Fetching source chunk metadata from Supabase ...")
    source_sections = fetch_source_sections(supabase, source_ids)

    print(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # Accumulators: hits[k] = count of entries where source was found in top-k
    hits = {k: 0 for k in KS}
    # precision_sum[k] = sum of per-entry precision@k scores
    precision_sum = {k: 0.0 for k in KS}
    # entries where source_chunk_id never appeared in top-MAX_K
    zero_recall_count = 0

    print(f"\nEvaluating {total} questions (this may take a minute) ...\n")

    for i, entry in enumerate(entries, 1):
        question = entry["question"]
        source_id = entry["source_chunk_id"]
        source_section = source_sections.get(source_id, "")

        query_vec: list[float] = model.encode(question, convert_to_numpy=True).tolist()

        response = supabase.rpc(
            "match_chunks",
            {"query_embedding": query_vec, "match_count": MAX_K},
        ).execute()

        results = response.data or []
        retrieved_ids = [r["id"] for r in results]
        retrieved_sections = [r.get("section", "") for r in results]

        found_at_any_k = source_id in retrieved_ids
        if not found_at_any_k:
            zero_recall_count += 1

        for k in KS:
            top_k_ids = retrieved_ids[:k]
            top_k_sections = retrieved_sections[:k]

            # Recall@k
            if source_id in top_k_ids:
                hits[k] += 1

            # Precision@k — fraction of top-k chunks sharing the source's section
            if top_k_sections and source_section:
                matching = sum(1 for s in top_k_sections if s == source_section)
                precision_sum[k] += matching / k
            # If source section is unknown, skip the entry for precision (don't penalise)

        if i % 10 == 0 or i == total:
            print(f"  [{i}/{total}] processed")

    # Compute final metrics
    recall = {k: hits[k] / total for k in KS}
    precision = {k: precision_sum[k] / total for k in KS}

    # ── Terminal output ──────────────────────────────────────────────────────
    header = f"{'Metric':<14}" + "".join(f"{'k='+str(k):>10}" for k in KS)
    sep = "-" * len(header)
    recall_row = f"{'Recall@k':<14}" + "".join(f"{recall[k]:>10.4f}" for k in KS)
    precision_row = f"{'Precision@k':<14}" + "".join(f"{precision[k]:>10.4f}" for k in KS)

    print()
    print("=" * len(header))
    print("  Baseline Retrieval Evaluation")
    print("=" * len(header))
    print(header)
    print(sep)
    print(recall_row)
    print(precision_row)
    print(sep)
    print(f"\nQuestions with 0 recall (source chunk not found at any k): {zero_recall_count}/{total}")

    # ── RESULTS.md ───────────────────────────────────────────────────────────
    results_path = Path("RESULTS.md")
    md_lines = [
        "# Groundwire — Retrieval Evaluation Results",
        "",
        "## Day 3 Baseline",
        "",
        "Day 3 baseline — before hybrid search + reranking (Week 2)",
        "",
        "| Metric | k=3 | k=5 | k=10 |",
        "|--------|-----|-----|------|",
        f"| Recall@k | {recall[3]:.4f} | {recall[5]:.4f} | {recall[10]:.4f} |",
        f"| Precision@k | {precision[3]:.4f} | {precision[5]:.4f} | {precision[10]:.4f} |",
        "",
        f"Questions with 0 recall (source chunk not found at any k): **{zero_recall_count}/{total}**",
        "",
        "### Notes",
        "- Recall@k: fraction of 80 golden-set questions where the source chunk appeared in the top-k results.",
        "- Precision@k: fraction of top-k retrieved chunks sharing the same section as the source chunk (section-match used as relevance proxy).",
        "- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine similarity via pgvector).",
    ]
    results_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nResults written to {results_path.resolve()}")


if __name__ == "__main__":
    main()
