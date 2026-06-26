"""
check_glossary_values.py
------------------------
Prints the REAL distinct values of the AACT columns referenced by the glossary,
so you can reconcile your glossary sql_hints against what the database stores.

Runs against AACT (NOT Supabase). From the project root:
    python crawler/check_glossary_values.py
"""

from phase1a_connect import run_query

# (label, SQL). Tables are unqualified because get_connection() sets
# search_path=ctgov, so `studies` resolves to ctgov.studies automatically.
CHECKS = [
    ("studies.overall_status",
     "SELECT overall_status, count(*) AS n FROM studies GROUP BY 1 ORDER BY n DESC"),
    ("studies.phase",
     "SELECT phase, count(*) AS n FROM studies GROUP BY 1 ORDER BY n DESC"),
    ("studies.study_type",
     "SELECT study_type, count(*) AS n FROM studies GROUP BY 1 ORDER BY n DESC"),
    ("sponsors.agency_class",
     "SELECT agency_class, count(*) AS n FROM sponsors GROUP BY 1 ORDER BY n DESC"),
    ("sponsors.lead_or_collaborator",
     "SELECT lead_or_collaborator, count(*) AS n FROM sponsors GROUP BY 1 ORDER BY n DESC"),
    ("interventions.intervention_type",
     "SELECT intervention_type, count(*) AS n FROM interventions GROUP BY 1 ORDER BY n DESC"),
    ("countries.name (top 10)",
     "SELECT name, count(*) AS n FROM countries GROUP BY 1 ORDER BY n DESC LIMIT 10"),
]


def main():
    for label, sql in CHECKS:
        print(f"\n=== {label} ===")
        _, rows = run_query(sql)
        for value, n in rows:
            print(f"  {str(value):40} {n:>12,}")
    print("\nReconcile any quoted literal in your glossary sql_hints with the values above.")


if __name__ == "__main__":
    main()