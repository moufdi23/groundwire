"""
Verify that the FastMCP app object in mcp_server.py has all three tools registered.

Run:
    python scripts/test_mcp_server.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server import mcp

EXPECTED = {"search_knowledge_base", "create_ticket", "check_status"}


def test_tools_registered():
    # FastMCP stores tools in mcp._tool_manager._tools (a dict keyed by tool name).
    registered = set(mcp._tool_manager._tools.keys())
    missing = EXPECTED - registered
    extra = registered - EXPECTED

    if missing:
        print(f"FAIL — missing tools: {missing}")
        sys.exit(1)
    if extra:
        print(f"NOTE — extra tools registered (not a failure): {extra}")

    print(f"PASS — all {len(EXPECTED)} tools registered: {sorted(registered)}")


if __name__ == "__main__":
    test_tools_registered()
