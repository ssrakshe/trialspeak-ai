"""
phase1b_schema_crawler.py
-------------------------
Reads the live AACT schema and turns each table into an embeddable "chunk":
a short, natural-language description + its columns + how it joins.

Output: output/schema_raw.json  (one chunk per table)
This file is the INPUT to Phase 1c, where each chunk_text gets embedded.
"""

import json
import os

from phase1a_connect import run_query

# --- Curated, human-written descriptions for the core tables. -----------------
# The live schema gives us column names and types, but not MEANING. These short
# descriptions (paraphrased from the AACT data dictionary) give each table the
# plain-English meaning that makes semantic retrieval work. Tables not listed
# here still get crawled - they just receive a generic description.
TABLE_DESCRIPTIONS = {
    "studies": "Central hub table, one row per clinical trial. High-level "
        "attributes: title, recruitment status, phase, study type, enrollment, "
        "sponsor source, and key dates (start, completion, first posted).",
    "conditions": "Diseases or conditions studied in each trial. One row per "
        "condition per trial (a trial can study several conditions).",
    "interventions": "Treatments tested in each trial - drugs, devices, "
        "procedures, behaviors. Includes intervention type and name.",
    "sponsors": "Organizations that fund or lead each trial, marked as lead or "
        "collaborator, with an agency class (industry, NIH, other).",
    "facilities": "Physical sites/locations where each trial is conducted, with "
        "name, city, state, country, and recruiting status.",
    "countries": "Countries in which each trial has sites. One row per country "
        "per trial.",
    "eligibilities": "Participant selection rules per trial: inclusion/exclusion "
        "criteria text, minimum and maximum age, sex, and healthy-volunteer flag.",
    "designs": "Study design details: allocation, intervention model, masking, "
        "and primary purpose.",
    "design_groups": "Protocol-defined arms, groups, or cohorts of participants "
        "assigned to interventions.",
    "design_outcomes": "Planned outcome measures (primary and secondary "
        "endpoints) defined at registration.",
    "outcomes": "Reported outcome results, including measured values per group "
        "after the study completed.",
    "brief_summaries": "A short plain-text summary of each study.",
    "detailed_descriptions": "A longer free-text description of each study's "
        "protocol.",
    "keywords": "Author-supplied keywords describing each trial.",
    "browse_conditions": "NLM-assigned MeSH condition terms - a standardized "
        "vocabulary for the diseases a trial addresses.",
    "browse_interventions": "NLM-assigned MeSH intervention terms - a "
        "standardized vocabulary for the treatments a trial uses.",
    "calculated_values": "AACT-computed fields such as number_of_facilities and "
        "actual_duration, derived from the raw data.",
    "central_contacts": "Contact people for enrollment questions (primary and "
        "backup) per trial.",
    "responsible_parties": "The party responsible for the trial (sponsor, PI, or "
        "sponsor-investigator) and their affiliation.",
    "id_information": "Secondary identifiers for each trial (other registry IDs, "
        "grant numbers, etc.).",
    "baseline_measurements": "Demographic and baseline measures collected per "
        "study group at the start of the trial (results data).",
    "drop_withdrawals": "Counts of how many participants withdrew, when, and why.",
}


def fetch_base_tables():
    """Return the list of real (non-view) table names in the ctgov schema."""
    sql = """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'ctgov' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    _, rows = run_query(sql)
    return [r[0] for r in rows]


def fetch_columns_by_table():
    """Return {table_name: [ {name, type, nullable}, ... ]} for all ctgov columns."""
    sql = """
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'ctgov'
        ORDER BY table_name, ordinal_position;
    """
    _, rows = run_query(sql)
    by_table = {}
    for table, col, dtype, nullable in rows:
        by_table.setdefault(table, []).append(
            {"name": col, "type": dtype, "nullable": (nullable == "YES")}
        )
    return by_table


def build_chunks(base_tables, columns_by_table):
    """Pure function: assemble one embeddable chunk per table. Easy to unit-test."""
    chunks = []
    for table in base_tables:
        columns = columns_by_table.get(table, [])
        col_names = [c["name"] for c in columns]
        has_nct_id = "nct_id" in col_names

        description = TABLE_DESCRIPTIONS.get(
            table, f"AACT auxiliary table '{table}'."
        )

        if table == "studies":
            relationship = "Central hub table; all other tables join to it via nct_id."
        elif has_nct_id:
            relationship = "Links to the studies table via nct_id."
        else:
            relationship = "No nct_id column; linked through another table's key."

        # The text that will actually be embedded in Phase 1c.
        col_list = ", ".join(c["name"] for c in columns)
        chunk_text = (
            f"Table: {table}\n"
            f"Description: {description}\n"
            f"Columns: {col_list}\n"
            f"Relationship: {relationship}"
        )

        chunks.append({
            "table_name": table,
            "description": description,
            "has_nct_id": has_nct_id,
            "relationship": relationship,
            "columns": columns,
            "chunk_text": chunk_text,
        })
    return chunks


def write_json(chunks, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)


def main():
    print("Crawling the live AACT schema...")
    base_tables = fetch_base_tables()
    columns_by_table = fetch_columns_by_table()
    chunks = build_chunks(base_tables, columns_by_table)

    out_path = os.path.join("output", "schema_raw.json")
    write_json(chunks, out_path)

    total_cols = sum(len(c["columns"]) for c in chunks)
    described = sum(1 for c in chunks if c["table_name"] in TABLE_DESCRIPTIONS)
    print(f"Wrote {len(chunks)} table chunks ({total_cols} columns total) to {out_path}")
    print(f"  {described} tables have curated descriptions; the rest use a generic one.")
    print("\nExample chunk_text:\n")
    print(chunks[0]["chunk_text"][:400])


if __name__ == "__main__":
    main()