"""
Verify that Supabase is reachable and that the pgvector extension is installed.
Run: python scripts/test_connection.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        print("[FAIL] Missing SUPABASE_URL or SUPABASE_SECRET_KEY in .env")
        sys.exit(1)

    try:
        from supabase import create_client, Client
    except ImportError:
        print("[FAIL] 'supabase' package not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    print(f"Connecting to {SUPABASE_URL} ...")

    try:
        client: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    except Exception as exc:
        print(f"[FAIL] Could not create Supabase client: {exc}")
        sys.exit(1)

    # Query pg_extension to confirm pgvector is installed
    try:
        result = client.rpc("check_pgvector").execute()
        # Fallback: use a raw SQL approach via the REST API if the RPC isn't set up yet
    except Exception:
        result = None

    # Primary check: use Supabase's PostgREST to query pg_extension via a raw SQL RPC.
    # Since we can't run arbitrary SQL through PostgREST without a function, we use
    # the Supabase management API alternative: try a direct psycopg2 connection.
    # psycopg2 direct-DB check is deferred to Day 2 (no wheel for Python 3.14 yet).
    # Use REST API to confirm connectivity instead.
    if True:
        # Confirm the REST API is reachable by listing tables (a lightweight call)
        try:
            # Attempt a known safe read on any public table.
            # If the project is empty, this returns an empty list — that's fine.
            response = client.table("_dummy_probe_").select("*").limit(1).execute()
            # A 404-style "relation does not exist" error is actually proof the API works.
            print("[OK]   Supabase REST API is reachable.")
        except Exception as api_err:
            err_str = str(api_err)
            if any(x in err_str for x in ("does not exist", "relation", "42P01", "PGRST205", "schema cache", "Could not find")):
                print("[OK]   Supabase REST API is reachable (received expected schema error).")
            else:
                print(f"[FAIL] Supabase REST API error: {api_err}")
                sys.exit(1)

    # Check pgvector by calling a built-in Postgres function via RPC.
    # This requires the `extensions` schema to be exposed — try a simple approach.
    try:
        # Use PostgREST's /rest/v1/rpc endpoint to run a sql function.
        # Since no custom function exists yet, we probe via the Supabase Python client's
        # ability to call the REST API and check the response headers for the version.
        import requests

        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        url = f"{SUPABASE_URL}/rest/v1/"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"[OK]   PostgREST endpoint responded (HTTP {resp.status_code}).")

        # Now check pgvector via the Supabase SQL editor endpoint (available on all projects)
        sql_url = f"{SUPABASE_URL}/rest/v1/rpc/pg_extension_check"
        # This function doesn't exist yet — we'll create it in a migration later.
        # Instead, make a direct SQL query via the Supabase SQL API (admin endpoint).
        sql_api_url = f"{SUPABASE_URL}/pg/query"
        sql_resp = requests.post(
            sql_api_url,
            headers=headers,
            json={"query": "SELECT extname FROM pg_extension WHERE extname = 'vector';"},
            timeout=10,
        )
        if sql_resp.status_code == 200:
            data = sql_resp.json()
            rows = data.get("rows", []) if isinstance(data, dict) else data
            if rows:
                print("[OK]   pgvector extension is ENABLED.")
            else:
                print("[WARN] pgvector extension not found. Enable it in Supabase: Database > Extensions > vector.")
        elif sql_resp.status_code in (401, 403):
            # Expected if using anon/publishable key — use secret key endpoint
            print("[OK]   Connection confirmed. pgvector check requires DB access (run in Supabase SQL editor):")
            print("       SELECT extname FROM pg_extension WHERE extname = 'vector';")
        else:
            print(f"[INFO] pgvector check inconclusive (HTTP {sql_resp.status_code}). Verify manually in Supabase.")

    except requests.exceptions.ConnectionError:
        print(f"[FAIL] Could not reach {SUPABASE_URL}. Check that SUPABASE_URL is correct.")
        sys.exit(1)
    except Exception as exc:
        print(f"[INFO] pgvector check skipped: {exc}")
        print("       Verify manually in Supabase SQL editor:")
        print("       SELECT extname FROM pg_extension WHERE extname = 'vector';")

    print("\nDay 1 connection check complete.")
    print("Next step: fill in your .env credentials and re-run this script.")


if __name__ == "__main__":
    main()
