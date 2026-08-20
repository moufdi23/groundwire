"""
Chunk every .md file in /data, embed with all-MiniLM-L6-v2, store in Supabase.

Run: python scripts/chunk_and_embed.py

Requires SUPABASE_URL and SUPABASE_SECRET_KEY in .env (service role key for writes).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client
from tqdm import tqdm

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# ~450 tokens × 4 chars/token = 1800 chars; 15% overlap = 270 chars
CHUNK_SIZE = 1800
CHUNK_OVERLAP = 270
EMBED_BATCH_SIZE = 64
INSERT_BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")
    return create_client(url, key)


def collect_chunks() -> list[dict]:
    """Read every .md file and split into chunks; return list of dicts."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )

    chunks: list[dict] = []
    md_files = sorted(DATA_DIR.rglob("*.md"))

    print(f"Found {len(md_files)} markdown files in {DATA_DIR}\n")

    for filepath in md_files:
        text = filepath.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue

        section = filepath.parent.name          # subfolder name
        source_file = str(filepath.relative_to(DATA_DIR.parent))  # e.g. data/auth/architecture.md

        split_texts = splitter.split_text(text)
        for piece in split_texts:
            piece = piece.strip()
            if len(piece) < 50:                 # discard tiny fragments
                continue
            chunks.append({
                "source_file": source_file,
                "section": section,
                "content": piece,
            })

    return chunks


def embed_chunks(chunks: list[dict], model: SentenceTransformer) -> list[dict]:
    """Add an 'embedding' key (list[float]) to each chunk dict."""
    texts = [c["content"] for c in chunks]
    embeddings: list[list[float]] = []

    print(f"Embedding {len(texts)} chunks in batches of {EMBED_BATCH_SIZE} ...")
    for start in tqdm(range(0, len(texts), EMBED_BATCH_SIZE), unit="batch"):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        vecs = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        embeddings.extend(vec.tolist() for vec in vecs)

    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb

    return chunks


def insert_chunks(supabase: Client, chunks: list[dict]) -> tuple[int, list[str]]:
    """Batch-insert chunks into Supabase; return (success_count, failure_messages)."""
    success = 0
    failures: list[str] = []

    print(f"\nInserting {len(chunks)} chunks into Supabase ...")
    for start in tqdm(range(0, len(chunks), INSERT_BATCH_SIZE), unit="batch"):
        batch = chunks[start : start + INSERT_BATCH_SIZE]
        try:
            supabase.table("chunks").insert(batch).execute()
            success += len(batch)
        except Exception as exc:
            msg = f"Batch {start}–{start+len(batch)-1}: {exc}"
            failures.append(msg)

    return success, failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== chunk_and_embed.py ===\n")

    # 1. Collect chunks
    chunks = collect_chunks()
    print(f"Total chunks after splitting: {len(chunks)}\n")

    if not chunks:
        sys.exit("No chunks produced — check that /data contains .md files.")

    # 2. Load model and embed
    print(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    chunks = embed_chunks(chunks, model)

    # 3. Connect to Supabase and insert
    supabase = load_supabase()
    success, failures = insert_chunks(supabase, chunks)

    # 4. Summary
    files_processed = len({c["source_file"] for c in chunks})
    print("\n--- Summary ---")
    print(f"Files processed     : {files_processed}")
    print(f"Total chunks created: {len(chunks)}")
    print(f"Chunks inserted OK  : {success}")
    print(f"Failures            : {len(failures)}")
    for msg in failures:
        print(f"  [FAIL] {msg}")

    if not failures:
        print("\nAll done. Run scripts/test_retrieval.py to verify retrieval.")


if __name__ == "__main__":
    main()
