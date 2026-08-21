"""
Generate a golden evaluation set from sampled Supabase chunks.

For each sampled chunk, calls Claude Haiku 4.5 to produce one realistic
support question and a short expected-answer summary.

Output: data/golden_set.jsonl  (80 entries)

Run: python scripts/generate_golden_set.py
"""

import json
import os
import random
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECTIONS = [
    "getting-started", "database", "auth", "storage", "functions",
    "realtime", "api", "ai", "self-hosting",
]
TOTAL_PAIRS = 80
MODEL = "claude-haiku-4-5"
MAX_CHUNK_CHARS = 600       # truncate chunk in prompt to control token cost
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "golden_set.jsonl"
API_CALL_DELAY = 0.25       # seconds between API calls — avoid burst rate limits

# Distribute 80 pairs across 9 sections as evenly as possible.
# 80 // 9 = 8 remainder 8  →  8 sections get 9 samples, 1 section gets 8.
_base = TOTAL_PAIRS // len(SECTIONS)
_extra = TOTAL_PAIRS % len(SECTIONS)
SAMPLES_PER_SECTION = {
    s: _base + (1 if i < _extra else 0) for i, s in enumerate(SECTIONS)
}


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def load_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("ERROR: Missing SUPABASE_URL or SUPABASE_SECRET_KEY in .env")
    return create_client(url, key)


def fetch_section_chunks(supabase: Client, section: str) -> list[dict]:
    """Return all chunks for a section from the 'chunks' table."""
    resp = (
        supabase.table("chunks")
        .select("id, section, source_file, content")
        .eq("section", section)
        .execute()
    )
    return resp.data or []


# ---------------------------------------------------------------------------
# Claude helpers
# ---------------------------------------------------------------------------

def build_prompt(chunk_content: str) -> str:
    snippet = chunk_content[:MAX_CHUNK_CHARS].strip()
    return (
        "You generate test data for a Supabase documentation support chatbot.\n\n"
        f"Documentation chunk:\n{snippet}\n\n"
        "Output a JSON object with exactly two keys:\n"
        '- "question": a realistic, specific question a developer would ask\n'
        '- "expected_answer_summary": 1-2 sentences summarizing the answer\n\n'
        "Output ONLY valid JSON — no markdown, no extra text."
    )


def generate_qa(claude: anthropic.Anthropic, chunk: dict) -> dict | None:
    """Call Claude Haiku to generate one Q/A pair for a chunk. Returns None on failure."""
    try:
        response = claude.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": build_prompt(chunk["content"])}],
        )
        text = response.content[0].text.strip()

        # Strip markdown code fences if the model wraps the JSON
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1].lstrip("json").strip() if len(parts) > 1 else text

        parsed = json.loads(text)
        return {
            "question": parsed["question"],
            "expected_answer_summary": parsed["expected_answer_summary"],
            "source_chunk_id": chunk["id"],
            "source_file": chunk["source_file"],
        }
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[parse error: {e}]")
        return None
    except anthropic.RateLimitError:
        print("[rate limited — waiting 10s]")
        time.sleep(10)
        return None
    except anthropic.APIStatusError as e:
        print(f"[API error {e.status_code}]")
        return None
    except anthropic.APIConnectionError:
        print("[connection error]")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== generate_golden_set.py ===\n")

    supabase = load_supabase()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: Missing ANTHROPIC_API_KEY in .env")
    claude = anthropic.Anthropic(api_key=api_key)

    # 1. Sample chunks from each section
    print("Sampling chunks from Supabase ...\n")
    all_samples: list[dict] = []
    section_sample_counts: dict[str, int] = {}

    for section in SECTIONS:
        n = SAMPLES_PER_SECTION[section]
        chunks = fetch_section_chunks(supabase, section)
        if not chunks:
            print(f"  [warn] no chunks found for section '{section}' — skipping")
            continue
        sampled = random.sample(chunks, min(n, len(chunks)))
        all_samples.extend(sampled)
        section_sample_counts[section] = len(sampled)
        print(f"  {section:<20} {len(chunks):>3} chunks available  →  sampled {len(sampled)}")

    print(f"\nTotal to process: {len(all_samples)}\n")
    random.shuffle(all_samples)  # randomize order so output isn't grouped by section

    # 2. Generate Q/A pairs and write to JSONL
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    results: list[dict] = []
    failures = 0
    section_generated: dict[str, int] = {s: 0 for s in SECTIONS}

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(all_samples, 1):
            section = chunk.get("section", "unknown")
            print(
                f"  [{i:>2}/{len(all_samples)}] chunk {chunk['id']} ({section}) ... ",
                end="",
                flush=True,
            )
            qa = generate_qa(claude, chunk)
            if qa:
                f.write(json.dumps(qa, ensure_ascii=False) + "\n")
                results.append(qa)
                section_generated[section] = section_generated.get(section, 0) + 1
                print("ok")
            else:
                failures += 1
                print("FAILED")

            if i < len(all_samples):
                time.sleep(API_CALL_DELAY)

    # 3. Summary
    print(f"\n{'=' * 40}")
    print("Summary")
    print(f"{'=' * 40}")
    print(f"  Pairs generated : {len(results)}")
    print(f"  Failures        : {failures}")
    print(f"  Output file     : {OUTPUT_PATH}")
    print()
    print("  Breakdown by section:")
    for section in SECTIONS:
        print(f"    {section:<20} {section_generated.get(section, 0):>2} pairs")

    if results:
        print("\nSample entry (first in output):")
        print(json.dumps(results[0], indent=2))


if __name__ == "__main__":
    main()
