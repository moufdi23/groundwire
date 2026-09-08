"""
Print the SQL needed to create the tables used by the Day 10 agent tools.
Run this script, then paste the output into the Supabase SQL Editor.

    python scripts/setup_tool_tables.py
"""

SQL = """
-- ============================================================
-- Day 10: tickets table for create_ticket / escalate_to_human
-- ============================================================

CREATE TABLE IF NOT EXISTS tickets (
    id         BIGSERIAL PRIMARY KEY,
    question   TEXT        NOT NULL,
    answer     TEXT        NOT NULL,
    reason     TEXT,                          -- NULL for auto-resolved; set for escalations
    status     TEXT        NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Optional: index for fast status lookups
CREATE INDEX IF NOT EXISTS tickets_status_idx ON tickets (status);

-- ============================================================
-- Verify (run after the CREATE above)
-- ============================================================
-- SELECT column_name, data_type, column_default
-- FROM   information_schema.columns
-- WHERE  table_name = 'tickets'
-- ORDER  BY ordinal_position;
"""

if __name__ == "__main__":
    print(SQL.strip())
    print()
    print("--- Paste the block above into Supabase SQL Editor and click Run. ---")
    print("The 'chunks' table already exists and is reused as-is for check_status lookups.")
