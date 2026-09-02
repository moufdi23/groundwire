"""
CI regression gate for retrieval quality.

Runs the full hybrid + reranking evaluation against the 80-question golden set
and compares results against fixed minimum thresholds.

Exit codes:
  0 — all thresholds passed
  1 — one or more thresholds breached (GitHub Actions marks the job as failed)

Thresholds (set ~3 pts below current Day-6 scores as a safety margin):
  recall@3    >= 0.88   (current: 0.9125)
  recall@10   >= 0.95   (current: 0.9875)
  precision@3 >= 0.75   (current: 0.8042)

No Claude API calls — only local embeddings + Supabase — so this is fast and
free to run on every push.

Run locally:
  python scripts/regression_check.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from reranked_search import reranked_retrieve, _ensure_cross_encoder
import hybrid_search as _hs
from hybrid_search import _ensure_initialized

load_dotenv()

GOLDEN_SET_PATH = Path("data/golden_set.jsonl")
KS = [3, 10]
MAX_K = max(KS)

THRESHOLDS = {
    "recall@3":    0.88,
    "recall@10":   0.95,
    "precision@3": 0.75,
}


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


def main() -> None:
    if not GOLDEN_SET_PATH.exists():
        sys.exit(f"ERROR: Golden set not found at {GOLDEN_SET_PATH}")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("ERROR: Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")

    print("=" * 60)
    print("  Groundwire — Retrieval Regression Check")
    print("=" * 60)

    print("\nLoading models and BM25 index ...")
    _ensure_initialized()
    _ensure_cross_encoder()
    supabase = _hs._supabase_client
    print("  Ready.")

    print("\nLoading golden set ...")
    entries = load_golden_set(GOLDEN_SET_PATH)
    total = len(entries)
    print(f"  {total} entries loaded.")

    source_ids = [e["source_chunk_id"] for e in entries]
    print("Fetching source chunk metadata from Supabase ...")
    source_sections = fetch_source_sections(supabase, source_ids)

    hits = {k: 0 for k in KS}
    precision_sum = {3: 0.0}  # only need precision@3 for the gate

    print(f"\nEvaluating {total} questions (cross-encoder runs on CPU — ~3-6 min) ...\n")

    for i, entry in enumerate(entries, 1):
        question = entry["question"]
        source_id = entry["source_chunk_id"]
        source_section = source_sections.get(source_id, "")

        results = reranked_retrieve(question, k=MAX_K)
        retrieved_ids = [r["id"] for r in results]
        retrieved_sections = [r["section"] for r in results]

        for k in KS:
            if source_id in retrieved_ids[:k]:
                hits[k] += 1

        # precision@3: fraction of top-3 chunks in the same section as the source
        top3_sections = retrieved_sections[:3]
        if top3_sections and source_section:
            matching = sum(1 for s in top3_sections if s == source_section)
            precision_sum[3] += matching / 3

        if i % 10 == 0 or i == total:
            print(f"  [{i}/{total}] processed")

    recall3  = hits[3]  / total
    recall10 = hits[10] / total
    prec3    = precision_sum[3] / total

    scores = {
        "recall@3":    recall3,
        "recall@10":   recall10,
        "precision@3": prec3,
    }

    # ── Results table ────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  {'Metric':<14} {'Score':>8}  {'Threshold':>10}  {'Status':>8}")
    print("-" * 60)

    all_passed = True
    for metric, score in scores.items():
        threshold = THRESHOLDS[metric]
        passed = score >= threshold
        if not passed:
            all_passed = False
        status = "PASS" if passed else "FAIL"
        print(f"  {metric:<14} {score:>8.4f}  {threshold:>10.4f}  {status:>8}")

    print("=" * 60)

    if all_passed:
        print("\nResult: ALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("\nResult: ONE OR MORE CHECKS FAILED — retrieval quality regression detected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
