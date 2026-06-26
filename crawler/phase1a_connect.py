"""
phase1a_connect.py
------------------
The single, reusable gateway to the AACT clinical-trials database.

Every script in this project gets its connection from here, so the connection
logic (credentials, SSL, search_path, timeouts) lives in exactly ONE place.
"""

import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv

# Load .env once, when this module is first imported.
load_dotenv()


def get_connection():
    """Open and return a new connection to AACT."""
    return psycopg2.connect(
        host=os.getenv("AACT_HOST"),
        port=os.getenv("AACT_PORT"),
        dbname=os.getenv("AACT_DBNAME"),
        user=os.getenv("AACT_USER"),
        password=os.getenv("AACT_PASSWORD"),
        sslmode="require",
        connect_timeout=10,
        # Make ctgov the default schema so we can write `studies`, not `ctgov.studies`.
        options="-c search_path=ctgov,public",
    )


@contextmanager
def aact_connection():
    """Context manager that guarantees the connection is closed afterwards."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql, params=None):
    """
    Run a read-only SQL query and return (column_names, rows).
    `params` is an optional tuple/dict for safe parameter substitution.
    """
    with aact_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
    return columns, rows


if __name__ == "__main__":
    cols, rows = run_query("SELECT count(*) AS n FROM studies;")
    print(f"Connected. The studies table has {rows[0][0]:,} rows.")