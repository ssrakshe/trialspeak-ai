"""
check_credentials.py
--------------------
Pre-flight check for the Clinical NL-to-SQL project.

Verifies that the services we depend on are reachable BEFORE we build
anything on top of them:
  1. AACT PostgreSQL  (the clinical-trials database we will query)
  2. OpenAI API       (the embeddings + LLM provider)
  3. Supabase         (our pgvector store, reached via its HTTPS API)

Run this first. If every check is green, the rest of the project is safe to build.
"""

import os
import sys
import urllib.request
import urllib.error

import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

# Load variables from the .env file in the project root into the environment.
load_dotenv()

# ANSI colors for readable terminal output.
GREEN, RED, YELLOW, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

def ok(msg):     print(f"{GREEN}  PASS {RESET}{msg}")
def fail(msg):   print(f"{RED}  FAIL {RESET}{msg}")
def warn(msg):   print(f"{YELLOW}  WARN {RESET}{msg}")
def header(msg): print(f"\n{msg}")

# Variables the project cannot run without.
REQUIRED_VARS = [
    "AACT_HOST", "AACT_PORT", "AACT_DBNAME", "AACT_USER", "AACT_PASSWORD",
    "OPENAI_API_KEY",
    "SUPABASE_URL", "SUPABASE_KEY",
]
# Nice to have, but not on the critical path (direct DB access for advanced use).
OPTIONAL_VARS = ["SUPABASE_DB_URL"]


def check_env_vars():
    """Return (missing_required, missing_optional)."""
    missing_required = [v for v in REQUIRED_VARS if not os.getenv(v)]
    missing_optional = [v for v in OPTIONAL_VARS if not os.getenv(v)]
    return missing_required, missing_optional


def check_aact():
    """Connect to AACT and count the studies table to prove read access."""
    conn = psycopg2.connect(
        host=os.getenv("AACT_HOST"),
        port=os.getenv("AACT_PORT"),
        dbname=os.getenv("AACT_DBNAME"),
        user=os.getenv("AACT_USER"),
        password=os.getenv("AACT_PASSWORD"),
        sslmode="require",
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ctgov.studies;")
            count = cur.fetchone()[0]
        ok(f"AACT connected - {count:,} clinical trials in the database")
    finally:
        conn.close()


def check_openai():
    """Make one tiny embedding call to prove the API key and endpoint work."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input="connection test",
    )
    dims = len(resp.data[0].embedding)
    if dims == 1536:
        ok(f"OpenAI connected - embedding returned {dims} dimensions (as expected)")
    else:
        warn(f"OpenAI connected but returned {dims} dims (expected 1536)")


def check_supabase():
    """
    Probe the Supabase REST API root with our project URL + key.
    This validates the exact credentials the supabase-py client uses,
    without needing any tables to exist yet. 200 = key accepted.
    """
    base = os.getenv("SUPABASE_URL").rstrip("/")
    key = os.getenv("SUPABASE_KEY")
    req = urllib.request.Request(
        f"{base}/rest/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                ok("Supabase REST API reachable and key accepted")
            else:
                warn(f"Supabase reachable but returned HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("API key rejected (401) - check SUPABASE_KEY") from e
        raise RuntimeError(f"HTTP {e.code} from Supabase") from e


def main():
    print("=" * 60)
    print(" Clinical NL-to-SQL - Credential Pre-flight Check")
    print("=" * 60)

    # 1) Fail fast on missing required vars; just warn on optional ones.
    missing_required, missing_optional = check_env_vars()
    header("Environment variables:")
    if missing_required:
        for v in missing_required:
            fail(f"{v} is missing or empty in your .env")
        print(f"\n{RED}Fix your .env file, then run this again.{RESET}")
        sys.exit(1)
    ok(f"All {len(REQUIRED_VARS)} required variables are present")
    for v in missing_optional:
        warn(f"{v} not set (optional - only needed for direct DB access)")

    # 2) Test each service independently so one failure doesn't mask the others.
    results = {}
    for name, fn in [
        ("AACT PostgreSQL", check_aact),
        ("OpenAI API", check_openai),
        ("Supabase", check_supabase),
    ]:
        header(f"{name}:")
        try:
            fn()
            results[name] = True
        except Exception as e:
            fail(f"{name} failed: {e}")
            results[name] = False

    # 3) Summary + exit code (0 = all good, 1 = something failed).
    print("\n" + "=" * 60)
    passed, total = sum(results.values()), len(results)
    if passed == total:
        print(f"{GREEN} All {total}/{total} services reachable. You're ready for Phase 1.{RESET}")
        sys.exit(0)
    print(f"{RED} {passed}/{total} services reachable. Fix the FAIL items above.{RESET}")
    sys.exit(1)


if __name__ == "__main__":
    main()