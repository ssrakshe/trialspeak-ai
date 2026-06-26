"""
phase1d_glossary.py
-------------------
Builds the SECOND vector store: a clinical glossary that maps plain-English
business terms to the exact SQL conditions the AACT database understands.

Prereq: run the (updated) config/supabase_setup.sql so glossary_chunks exists.

IMPORTANT: the literal strings in each `sql_hint` (e.g. 'Recruiting', 'Phase 3',
'INDUSTRY') must match what YOUR database actually stores. Verify against the
distinct values you saw in Step 2, and against quick GROUP BY checks, before
trusting these defaults.
"""

import json
import os

from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

from phase1c_embed_schema import embed_texts  # reuse the batched embedder

load_dotenv()

# --- The glossary. Three kinds of mapping are represented on purpose:
#     (1) simple column-value, (2) join-based, (3) computed/range. ---------------
GLOSSARY = [
    # (1) Simple status mappings
    {"term": "active trial",
     "synonyms": "ongoing trial, currently running, in progress, live study",
     "explanation": "A trial currently underway - still recruiting or treating participants.",
     "sql_hint": "studies.overall_status IN ('RECRUITING','ACTIVE_NOT_RECRUITING','ENROLLING_BY_INVITATION')"},
    {"term": "recruiting trial",
     "synonyms": "open for enrollment, accepting patients, enrolling now",
     "explanation": "A trial actively seeking and enrolling new participants.",
     "sql_hint": "studies.overall_status = 'RECRUITING'"},
    {"term": "completed trial",
     "synonyms": "finished study, concluded trial, done",
     "explanation": "A trial that ended normally with participants having finished.",
     "sql_hint": "studies.overall_status = 'COMPLETED'"},
    {"term": "stopped trial",
     "synonyms": "terminated, halted, suspended, withdrawn, discontinued early",
     "explanation": "A trial that ended early or was halted before normal completion.",
     "sql_hint": "studies.overall_status IN ('TERMINATED','SUSPENDED','WITHDRAWN')"},

    # (1) Phase mappings
    {"term": "phase 3 trial",
     "synonyms": "phase III, pivotal trial, late-stage efficacy trial",
     "explanation": "A large trial testing efficacy and safety before approval.",
     "sql_hint": "studies.phase = 'PHASE3'"},
    {"term": "early-stage trial",
     "synonyms": "phase 1, phase I, first-in-human, early phase",
     "explanation": "An early safety and dosing trial in a small group.",
     "sql_hint": "studies.phase IN ('EARLY_PHASE1','PHASE1')"},
    {"term": "late-stage trial",
     "synonyms": "phase 3, phase 4, advanced, post-approval",
     "explanation": "Trials in later development stages or after approval.",
     "sql_hint": "studies.phase IN ('PHASE3','PHASE4')"},

    # (1) Study type
    {"term": "interventional study",
     "synonyms": "treatment study, experimental study, clinical trial with intervention",
     "explanation": "A study where participants are assigned to receive an intervention.",
     "sql_hint": "studies.study_type = 'INTERVENTIONAL'"},
    {"term": "observational study",
     "synonyms": "non-interventional, cohort study, registry study",
     "explanation": "A study that observes outcomes without assigning interventions.",
     "sql_hint": "studies.study_type = 'OBSERVATIONAL'"},

    # (2) Join-based: conditions
    {"term": "cancer trial",
     "synonyms": "oncology study, tumor trial, neoplasm, carcinoma, malignancy",
     "explanation": "A trial studying cancer; match condition names for cancer terms.",
     "sql_hint": "JOIN conditions c ON c.nct_id = studies.nct_id WHERE c.downcase_name ~ 'cancer|oncolog|tumor|neoplasm|carcinoma'"},
    {"term": "diabetes trial",
     "synonyms": "diabetic study, type 2 diabetes, T2DM, blood sugar",
     "explanation": "A trial studying diabetes.",
     "sql_hint": "JOIN conditions c ON c.nct_id = studies.nct_id WHERE c.downcase_name LIKE '%diabet%'"},

    # (2) Join-based: sponsors
    {"term": "industry-sponsored trial",
     "synonyms": "big pharma, commercial sponsor, company-funded, pharmaceutical company",
     "explanation": "A trial led by a for-profit company rather than academia or government.",
     "sql_hint": "JOIN sponsors sp ON sp.nct_id = studies.nct_id WHERE sp.lead_or_collaborator = 'lead' AND sp.agency_class = 'INDUSTRY'"},
    {"term": "NIH-funded trial",
     "synonyms": "government funded, federally funded, National Institutes of Health",
     "explanation": "A trial sponsored by the U.S. National Institutes of Health.",
     "sql_hint": "JOIN sponsors sp ON sp.nct_id = studies.nct_id WHERE sp.agency_class = 'NIH'"},

    # (2) Join-based: interventions and location
    {"term": "drug trial",
     "synonyms": "pharmaceutical trial, medication study, biologic",
     "explanation": "A trial testing a drug or biologic intervention.",
     "sql_hint": "JOIN interventions i ON i.nct_id = studies.nct_id WHERE i.intervention_type IN ('DRUG','BIOLOGICAL')"},
    {"term": "US-based trial",
     "synonyms": "United States, American trial, trials in the USA, US sites",
     "explanation": "A trial with at least one site in the United States.",
     "sql_hint": "JOIN countries co ON co.nct_id = studies.nct_id WHERE co.name = 'United States'"},

    # (3) Computed / range
    {"term": "large trial",
     "synonyms": "big enrollment, many participants, high enrollment",
     "explanation": "A trial enrolling a large number of participants (>= 1000).",
     "sql_hint": "studies.enrollment >= 1000"},
    {"term": "small trial",
     "synonyms": "few participants, low enrollment, pilot study",
     "explanation": "A trial enrolling few participants (< 100).",
     "sql_hint": "studies.enrollment < 100"},
    {"term": "recently started trial",
     "synonyms": "new trial, started this year, recent study",
     "explanation": "A trial that started within roughly the last year.",
     "sql_hint": "studies.start_date >= (CURRENT_DATE - INTERVAL '1 year')"},
    {"term": "trial with results",
     "synonyms": "has posted results, results available, reported outcomes",
     "explanation": "A trial that has submitted results to the registry.",
     "sql_hint": "studies.results_first_submitted_date IS NOT NULL"},
]


def build_chunk_text(entry):
    """The text we embed: heavy on natural language so user questions match it."""
    return (
        f"Term: {entry['term']} (also called: {entry['synonyms']}).\n"
        f"Meaning: {entry['explanation']}\n"
        f"SQL condition: {entry['sql_hint']}"
    )


def main():
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    chunk_texts = [build_chunk_text(e) for e in GLOSSARY]
    print(f"Embedding {len(chunk_texts)} glossary terms...")
    vectors = embed_texts(openai_client, chunk_texts)

    rows = [
        {
            "term": e["term"],
            "sql_hint": e["sql_hint"],
            "chunk_text": ct,
            "embedding": json.dumps(v),
        }
        for e, ct, v in zip(GLOSSARY, chunk_texts, vectors)
    ]

    supabase.table("glossary_chunks").delete().gt("id", 0).execute()
    supabase.table("glossary_chunks").insert(rows).execute()
    print(f"Inserted {len(rows)} glossary terms into glossary_chunks. Phase 1d complete.")


if __name__ == "__main__":
    main()