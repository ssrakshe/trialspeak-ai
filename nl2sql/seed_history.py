"""
seed_history.py
---------------
Bootstrap the query-history store with hand-verified (question -> SQL) examples
that use the CORRECT uppercase literals. Gives the generator good few-shot
examples from the very first query (and teaches correct casing).

Verify each literal against your check_glossary_values.py output before trusting.
"""

from retrieval import get_clients, save_query

SEED = [
    ("How many trials are currently recruiting?",
     "SELECT COUNT(*) FROM studies WHERE overall_status = 'RECRUITING';"),
    ("How many Phase 3 trials are there?",
     "SELECT COUNT(*) FROM studies WHERE phase = 'PHASE3';"),
    ("How many trials are sponsored by industry?",
     "SELECT COUNT(DISTINCT s.nct_id) FROM studies s "
     "JOIN sponsors sp ON sp.nct_id = s.nct_id WHERE sp.agency_class = 'INDUSTRY';"),
    ("List 10 completed interventional drug trials.",
     "SELECT DISTINCT s.nct_id, s.brief_title FROM studies s "
     "JOIN interventions i ON i.nct_id = s.nct_id "
     "WHERE s.overall_status = 'COMPLETED' AND s.study_type = 'INTERVENTIONAL' "
     "AND i.intervention_type = 'DRUG' LIMIT 10;"),
    ("Which trials were terminated and why?",
     "SELECT nct_id, brief_title, why_stopped FROM studies "
     "WHERE overall_status = 'TERMINATED' LIMIT 20;"),
]


def main():
    openai_client, supabase = get_clients()
    for question, sql in SEED:
        save_query(openai_client, supabase, question, sql)
        print(f"Seeded: {question}")
    print(f"\nDone. Seeded {len(SEED)} example queries into query_history.")


if __name__ == "__main__":
    main()