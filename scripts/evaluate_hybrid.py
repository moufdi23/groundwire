"""
Hybrid retrieval evaluation against the golden set.

Loads data/golden_set.jsonl (80 entries), runs each question through
hybrid_retrieve (vector + BM25 with RRF), and computes recall@k and
precision@k for k in {3, 5, 10}.

Appends Day 5 results to RESULTS.md with a delta table vs the Day 3 baseline.

Run: python scripts/evaluate_hybrid.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# hybrid_search lives alongside this script; Python adds scripts/ to sys.path
# automatically when running `python scripts/evaluate_hybrid.py`.
from hybrid_search import hybrid_retrieve, _ensure_initialized
import hybrid_search as _hs

load_dotenv()

GOLDEN_SET_PATH = Path("data/golden_set.jsonl")
KS = [3, 5, 10]
MAX_K = max(KS)

# Day 3 baseline values — hardcoded so the delta table is always accurate
# even if RESULTS.md is regenerated.
BASELINE_RECALL = {3: 0.8125, 5: 0.8750, 10: 0.8875}
BASELINE_PRECISION = {3: 0.7625, 5: 0.6775, 10: 0.5963}


def load_golden_set(path: Path) -> list[dict]:
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def fetch_source_sections(supabase, chunk_ids: list[int]) -> dict[int, str]:
    response = (
        supabase.table("chunks")
        .select("id, section")
        .in_("id", chunk_ids)
        .execute()
    )
    return {row["id"]: row.get("section", "") for row in response.data}


def _delta(new: float, old: float) -> str:
    d = new - old
    sign = "+" if d >= 0 else ""
    return f"{sign}{d * 100:.1f} pts"


def main() -> None:
    if not GOLDEN_SET_PATH.exists():
        sys.exit(f"Golden set not found at {GOLDEN_SET_PATH}")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")

    # Prime the lazy initializer so the model + BM25 index load once up front.
    _ensure_initialized()
    supabase = _hs._supabase_client

    print("Loading golden set ...")
    entries = load_golden_set(GOLDEN_SET_PATH)
    total = len(entries)
    print(f"  {total} entries loaded.")

    source_ids = [e["source_chunk_id"] for e in entries]
    print("Fetching source chunk metadata from Supabase ...")
    source_sections = fetch_source_sections(supabase, source_ids)

    hits = {k: 0 for k in KS}
    precision_sum = {k: 0.0 for k in KS}
    zero_recall_count = 0

    print(f"\nEvaluating {total} questions (this may take a couple of minutes) ...\n")

    for i, entry in enumerate(entries, 1):
        question = entry["question"]
        source_id = entry["source_chunk_id"]
        source_section = source_sections.get(source_id, "")

        results = hybrid_retrieve(question, k=MAX_K)
        retrieved_ids = [r["id"] for r in results]
        retrieved_sections = [r["section"] for r in results]

        if source_id not in retrieved_ids:
            zero_recall_count += 1

        for k in KS:
            top_k_ids = retrieved_ids[:k]
            top_k_sections = retrieved_sections[:k]

            if source_id in top_k_ids:
                hits[k] += 1

            if top_k_sections and source_section:
                matching = sum(1 for s in top_k_sections if s == source_section)
                precision_sum[k] += matching / k

        if i % 10 == 0 or i == total:
            print(f"  [{i}/{total}] processed")

    recall = {k: hits[k] / total for k in KS}
    precision = {k: precision_sum[k] / total for k in KS}

    # ── Terminal output ──────────────────────────────────────────────────────
    header = f"{'Metric':<14}" + "".join(f"{'k='+str(k):>10}" for k in KS)
    sep = "-" * len(header)
    recall_row = f"{'Recall@k':<14}" + "".join(f"{recall[k]:>10.4f}" for k in KS)
    precision_row = f"{'Precision@k':<14}" + "".join(f"{precision[k]:>10.4f}" for k in KS)

    print()
    print("=" * len(header))
    print("  Day 5 — Hybrid Retrieval (Vector + BM25 with RRF)")
    print("=" * len(header))
    print(header)
    print(sep)
    print(recall_row)
    print(precision_row)
    print(sep)
    print(f"\nQuestions with 0 recall: {zero_recall_count}/{total}")
    print()
    print("Delta vs Day 3 baseline:")
    for k in KS:
        print(
            f"  recall@{k}:    {BASELINE_RECALL[k]:.4f} → {recall[k]:.4f}"
            f"  ({_delta(recall[k], BASELINE_RECALL[k])})"
        )
    for k in KS:
        print(
            f"  precision@{k}: {BASELINE_PRECISION[k]:.4f} → {precision[k]:.4f}"
            f"  ({_delta(precision[k], BASELINE_PRECISION[k])})"
        )

    # ── Append to RESULTS.md ─────────────────────────────────────────────────
    results_path = Path("RESULTS.md")
    existing = results_path.read_text(encoding="utf-8") if results_path.exists() else ""

    # Strip any prior Day 5 section so re-runs don't duplicate it.
    if "## Day 5" in existing:
        existing = existing[: existing.index("## Day 5")].rstrip()

    new_section = "\n".join([
        "",
        "## Day 5 — Hybrid Search (Vector + BM25 with RRF)",
        "",
        "| Metric | k=3 | k=5 | k=10 |",
        "|--------|-----|-----|------|",
        f"| Recall@k | {recall[3]:.4f} | {recall[5]:.4f} | {recall[10]:.4f} |",
        f"| Precision@k | {precision[3]:.4f} | {precision[5]:.4f} | {precision[10]:.4f} |",
        "",
        f"Questions with 0 recall: **{zero_recall_count}/{total}**",
        "",
        "### Delta vs Day 3 Baseline",
        (
            f"- recall@3:    {BASELINE_RECALL[3]:.4f} → {recall[3]:.4f}"
            f"  ({_delta(recall[3], BASELINE_RECALL[3])})"
        ),
        (
            f"- recall@5:    {BASELINE_RECALL[5]:.4f} → {recall[5]:.4f}"
            f"  ({_delta(recall[5], BASELINE_RECALL[5])})"
        ),
        (
            f"- recall@10:   {BASELINE_RECALL[10]:.4f} → {recall[10]:.4f}"
            f"  ({_delta(recall[10], BASELINE_RECALL[10])})"
        ),
        (
            f"- precision@3: {BASELINE_PRECISION[3]:.4f} → {precision[3]:.4f}"
            f"  ({_delta(precision[3], BASELINE_PRECISION[3])})"
        ),
        (
            f"- precision@5: {BASELINE_PRECISION[5]:.4f} → {precision[5]:.4f}"
            f"  ({_delta(precision[5], BASELINE_PRECISION[5])})"
        ),
        (
            f"- precision@10: {BASELINE_PRECISION[10]:.4f} → {precision[10]:.4f}"
            f"  ({_delta(precision[10], BASELINE_PRECISION[10])})"
        ),
        "",
        "### Notes",
        "- Fusion: Reciprocal Rank Fusion (RRF, k=60), vector pool=50, BM25 pool=50.",
        "- BM25 index: `data/bm25_index.pkl` (BM25Okapi via rank_bm25).",
        "- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine similarity via pgvector).",
    ])

    results_path.write_text(existing + "\n" + new_section + "\n", encoding="utf-8")
    print(f"\nResults appended to {results_path.resolve()}")


if __name__ == "__main__":
    main()
