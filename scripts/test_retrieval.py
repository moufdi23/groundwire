"""
Manual smoke-test for the retrieval pipeline.

Embeds a hardcoded query, calls the match_chunks RPC function in Supabase,
and prints the top-5 most similar chunks.

Prerequisite: run the SQL below in the Supabase SQL editor ONCE before using
this script.

------------------------------------------------------------------
  SQL to run in Supabase → SQL Editor → New query:

  CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(384),
    match_count     int DEFAULT 5
  )
  RETURNS TABLE (
    id          bigint,
    source_file text,
    section     text,
    content     text,
    similarity  float
  )
  LANGUAGE sql STABLE
  AS $$
    SELECT
      id,
      source_file,
      section,
      content,
      1 - (embedding <=> query_embedding) AS similarity
    FROM chunks
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
  $$;
------------------------------------------------------------------

Run this script: python scripts/test_retrieval.py
"""

import os
import sys
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client

load_dotenv()

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TEST_QUERY = "How do I enable row level security?"
TOP_K = 5
PREVIEW_CHARS = 300


def main() -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment.")

    supabase = create_client(url, key)

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print(f'\nEmbedding query: "{TEST_QUERY}"')
    query_vec: list[float] = model.encode(TEST_QUERY, convert_to_numpy=True).tolist()

    print(f"Querying Supabase for top {TOP_K} chunks ...\n")
    response = supabase.rpc(
        "match_chunks",
        {"query_embedding": query_vec, "match_count": TOP_K},
    ).execute()

    results = response.data
    if not results:
        print("No results returned. Did you run chunk_and_embed.py first?")
        return

    print(f"{'='*60}")
    for i, row in enumerate(results, 1):
        similarity = row.get("similarity", 0.0)
        source = row.get("source_file", "unknown")
        content = row.get("content", "")
        preview = content[:PREVIEW_CHARS].replace("\n", " ")
        if len(content) > PREVIEW_CHARS:
            preview += " ..."

        print(f"[{i}] similarity={similarity:.4f}  source={source}")
        print(f"     {preview}")
        print()


if __name__ == "__main__":
    main()
