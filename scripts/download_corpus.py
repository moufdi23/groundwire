"""
Download Supabase documentation as clean text into /data.

Source: raw MDX files from github.com/supabase/supabase
These are the same files that power supabase.com/docs — fetching from GitHub
avoids having to parse a JavaScript-rendered site and gives us clean markdown.

Run: python scripts/download_corpus.py
Output: data/<section>/<slug>.md  (30-60 files, ~1-3 MB total)
"""

import os
import re
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_BASE = "https://raw.githubusercontent.com/supabase/supabase/master/apps/docs/content/guides"
API_BASE = "https://api.github.com/repos/supabase/supabase/git/trees/master?recursive=1"

DATA_DIR = Path(__file__).parent.parent / "data"

# Core guide sections to download (section_name: github_path_prefix)
SECTIONS = {
    "getting-started": "apps/docs/content/guides/getting-started",
    "database":        "apps/docs/content/guides/database",
    "auth":            "apps/docs/content/guides/auth",
    "storage":         "apps/docs/content/guides/storage",
    "functions":       "apps/docs/content/guides/functions",
    "realtime":        "apps/docs/content/guides/realtime",
    "api":             "apps/docs/content/guides/api",
    "ai":              "apps/docs/content/guides/ai",
    "self-hosting":    "apps/docs/content/guides/self-hosting",
}

# Max files per section so we stay in the 30-60 page target
MAX_PER_SECTION = 8

REQUEST_DELAY = 0.3  # seconds between downloads — be a polite scraper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_mdx(raw: str) -> str:
    """Remove MDX/JSX imports and component tags; keep prose and markdown."""
    # Strip YAML frontmatter
    raw = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL)

    # Remove import statements
    raw = re.sub(r"^import\s+.*?$", "", raw, flags=re.MULTILINE)

    # Remove JSX/MDX component blocks like <Admonition ...>...</Admonition>
    # Keep their text content when possible
    raw = re.sub(r"<([A-Z][A-Za-z]+)[^>]*/?>", "", raw)
    raw = re.sub(r"</[A-Z][A-Za-z]+>", "", raw)

    # Remove inline JSX expressions {/* comment */} and {variable}
    raw = re.sub(r"\{/\*.*?\*/\}", "", raw, flags=re.DOTALL)
    raw = re.sub(r"\{[^}]{0,120}\}", "", raw)

    # Collapse excessive blank lines
    raw = re.sub(r"\n{3,}", "\n\n", raw)

    return raw.strip()


def fetch_file_list() -> list[dict]:
    """Fetch the full repo tree from GitHub and return matching .mdx files."""
    print("Fetching file tree from GitHub API ...")
    headers = {"Accept": "application/vnd.github.v3+json"}
    # GitHub token is optional but avoids rate limits (60 req/hr unauthenticated)
    gh_token = os.getenv("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    resp = requests.get(API_BASE, headers=headers, timeout=30)
    if resp.status_code == 403:
        print("[WARN] GitHub API rate-limited. Using hardcoded file list instead.")
        return []
    resp.raise_for_status()

    tree = resp.json().get("tree", [])
    matched = []
    for item in tree:
        if item["type"] != "blob":
            continue
        path: str = item["path"]
        if not path.endswith((".mdx", ".md")):
            continue
        for section_name, prefix in SECTIONS.items():
            if path.startswith(prefix):
                matched.append({"section": section_name, "path": path})
                break
    return matched


def hardcoded_file_list() -> list[dict]:
    """Fallback list of ~50 core doc pages when the API is unavailable."""
    entries = [
        # getting-started
        ("getting-started", "quickstarts/nextjs"),
        ("getting-started", "quickstarts/react"),
        ("getting-started", "quickstarts/python"),
        ("getting-started", "features"),
        ("getting-started", "architecture"),
        # database
        ("database", "overview"),
        ("database", "tables"),
        ("database", "views"),
        ("database", "functions"),
        ("database", "triggers"),
        ("database", "indexes"),
        ("database", "extensions/pgvector"),
        ("database", "extensions/pg_trgm"),
        ("database", "extensions/uuid-ossp"),
        ("database", "postgres-changes"),
        ("database", "row-level-security"),
        ("database", "json"),
        ("database", "full-text-search"),
        ("database", "managing-passwords"),
        # auth
        ("auth", "overview"),
        ("auth", "users"),
        ("auth", "sessions"),
        ("auth", "signing-in"),
        ("auth", "social-login"),
        ("auth", "email-login"),
        ("auth", "phone-login"),
        ("auth", "magic-link"),
        ("auth", "row-level-security"),
        ("auth", "server-side"),
        ("auth", "multi-factor-authentication"),
        # storage
        ("storage", "overview"),
        ("storage", "buckets"),
        ("storage", "uploads"),
        ("storage", "downloads"),
        ("storage", "access-control"),
        ("storage", "cdn"),
        ("storage", "image-transformations"),
        # functions
        ("functions", "overview"),
        ("functions", "quickstart"),
        ("functions", "routing"),
        ("functions", "auth"),
        ("functions", "secrets"),
        # realtime
        ("realtime", "overview"),
        ("realtime", "broadcast"),
        ("realtime", "presence"),
        ("realtime", "postgres-changes"),
        # api
        ("api", "creating-routes"),
        # ai
        ("ai", "overview"),
        ("ai", "vector-embeddings"),
        ("ai", "semantic-search"),
        ("ai", "pgvector"),
        ("ai", "choosing-compute-addon"),
    ]
    result = []
    for section, slug in entries:
        result.append({
            "section": section,
            "path": f"apps/docs/content/guides/{section}/{slug}.mdx",
        })
    return result


def download_file(path: str) -> str | None:
    """Download a single file from GitHub raw content."""
    url = f"https://raw.githubusercontent.com/supabase/supabase/master/{path}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            # Try .md extension as fallback
            url_md = url.replace(".mdx", ".md")
            resp = requests.get(url_md, timeout=15)
        if resp.status_code != 200:
            return None
        return resp.text
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    # Attempt API fetch; fall back to hardcoded list
    files = fetch_file_list()
    if not files:
        print("Using hardcoded file list (API unavailable or rate-limited).")
        files = hardcoded_file_list()

    # Enforce per-section limits and build download queue
    counts: dict[str, int] = {s: 0 for s in SECTIONS}
    queue: list[dict] = []
    for f in files:
        section = f["section"]
        if counts[section] < MAX_PER_SECTION:
            queue.append(f)
            counts[section] += 1

    print(f"\nDownloading {len(queue)} files ...\n")

    success = 0
    skipped = 0

    for item in queue:
        section = item["section"]
        path = item["path"]

        # Derive a clean output filename from the GitHub path
        # e.g. apps/docs/content/guides/database/extensions/pgvector.mdx
        #   -> data/database/extensions__pgvector.md
        relative = path.replace(f"apps/docs/content/guides/{section}/", "")
        slug = relative.replace("/", "__").replace(".mdx", "").replace(".md", "")
        out_dir = DATA_DIR / section
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{slug}.md"

        if out_path.exists():
            print(f"  [skip] {section}/{slug}.md (already downloaded)")
            skipped += 1
            continue

        raw = download_file(path)
        if raw is None:
            print(f"  [miss] {path}")
            continue

        clean = strip_mdx(raw)
        if len(clean) < 100:
            # File is essentially empty after stripping — skip it
            print(f"  [empty] {section}/{slug}")
            continue

        out_path.write_text(clean, encoding="utf-8")
        kb = len(clean) / 1024
        print(f"  [ok]   {section}/{slug}.md  ({kb:.1f} KB)")
        success += 1
        time.sleep(REQUEST_DELAY)

    print(f"\nDone. {success} files saved to {DATA_DIR}, {skipped} skipped.")
    total_kb = sum(
        f.stat().st_size for f in DATA_DIR.rglob("*.md")
    ) / 1024
    print(f"Total corpus size: {total_kb:.0f} KB across {success + skipped} files.")
    print("\nNext step (Day 2): chunk these files and embed them into Supabase.")


if __name__ == "__main__":
    main()
