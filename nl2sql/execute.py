"""
execute.py
----------
Safety validation + execution of generated SQL against AACT.

Two layers of protection before we run anything:
  1. is_safe_select(): a programmatic guard - SELECT-only, single statement.
  2. AACT itself grants public users READ-ONLY access, so the database is the
     ultimate backstop even if a check were bypassed (defense in depth).
"""

import re
import sys
import pathlib

# The executor needs the AACT connection, which lives in the crawler package.
# Add the project root to the path so `crawler.phase1a_connect` is importable.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from crawler.phase1a_connect import aact_connection  # noqa: E402

# Keywords that must never appear in a read-only analytics query.
FORBIDDEN = (
    "insert", "update", "delete", "drop", "alter",
    "truncate", "grant", "revoke", "create", "merge", "copy",
)


def is_safe_select(sql):
    """Return (is_safe, reason). Accepts a single SELECT/WITH statement only."""
    if not sql or not sql.strip():
        return False, "Empty query."

    s = sql.strip().rstrip(";").strip()
    low = s.lower()

    if not (low.startswith("select") or low.startswith("with")):
        return False, "Query must start with SELECT (or a WITH/CTE)."

    if ";" in s:  # trailing ';' already stripped, so this means MULTIPLE statements
        return False, "Multiple statements are not allowed."

    for kw in FORBIDDEN:
        if re.search(rf"\b{kw}\b", low):
            return False, f"Forbidden keyword detected: {kw}."

    return True, "ok"


def run_sql(sql, max_rows=100):
    """Execute a validated SELECT against AACT; return (columns, rows)."""
    with aact_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(max_rows)   # cap rows pulled into memory
    return columns, rows