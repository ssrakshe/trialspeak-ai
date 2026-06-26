"""
explore_schema.py
-----------------
Phase 1a exploration: open AACT and look at what is really inside.
"""

from phase1a_connect import run_query


def list_tables():
    print("\n=== TABLES in the ctgov schema (approximate row counts) ===")
    sql = """
        SELECT c.relname AS table_name, c.reltuples::bigint AS approx_rows
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'ctgov' AND c.relkind = 'r'
        ORDER BY c.relname;
    """
    _, rows = run_query(sql)
    for name, approx in rows:
        print(f"  {name:34} {approx:>14,}")
    print(f"\n  Total: {len(rows)} tables.")


def describe_studies():
    print("\n=== COLUMNS of the `studies` table ===")
    sql = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'ctgov' AND table_name = 'studies'
        ORDER BY ordinal_position;
    """
    _, rows = run_query(sql)
    for name, dtype, nullable in rows:
        print(f"  {name:32} {dtype:22} nullable={nullable}")
    print(f"\n  {len(rows)} columns.")


def show_vocabulary():
    for column in ("overall_status", "study_type", "phase"):
        print(f"\n=== Distinct values of studies.{column} ===")
        sql = f"""
            SELECT COALESCE({column}::text, '(null)') AS value, count(*) AS n
            FROM studies
            GROUP BY {column}
            ORDER BY n DESC;
        """
        _, rows = run_query(sql)
        for value, n in rows:
            print(f"  {value:34} {n:>12,}")


def show_relationship_example():
    print("\n=== One study joined to its conditions + sponsors (via nct_id) ===")
    sql = """
        SELECT s.nct_id, s.overall_status, c.name AS condition, sp.name AS sponsor
        FROM studies s
        LEFT JOIN conditions c  ON c.nct_id  = s.nct_id
        LEFT JOIN sponsors  sp ON sp.nct_id = s.nct_id
        WHERE s.brief_title IS NOT NULL
        LIMIT 6;
    """
    cols, rows = run_query(sql)
    print("  " + " | ".join(cols))
    for r in rows:
        print("  " + " | ".join(str(x) for x in r))


def main():
    list_tables()
    describe_studies()
    show_vocabulary()
    show_relationship_example()
    print("\nDone. You now know the shape of the data we will teach the system.")


if __name__ == "__main__":
    main()