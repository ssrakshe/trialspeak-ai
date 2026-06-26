"""
test_retrieval.py
-----------------
Phase 1 validation gate: prove that both vector stores return the RIGHT context
for real stakeholder questions, BEFORE we build the SQL generator.

For each question we:
  1. embed it,
  2. retrieve the most similar SCHEMA chunks  (which tables?),
  3. retrieve the most similar GLOSSARY terms (what do the words mean?),
and print them so you can judge the quality with your own eyes.
"""

import json
import os

from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

from phase1c_embed_schema import embed_texts

load_dotenv()

# Real questions a medical director / safety officer / investor might ask.
QUESTIONS = [
    "How many Phase 3 cancer trials are currently recruiting?",
    "Which industry-sponsored diabetes trials were completed recently?",
    "List large interventional drug trials that have results posted.",
    "What conditions are most common in US-based trials?",
    "Show me trials that were terminated early.",
]

TOP_K = 3


def embed_one(openai_client, text):
    """Embed a single string -> one 1536-dim vector."""
    return embed_texts(openai_client, [text])[0]


def retrieve(supabase, rpc_name, query_vec, k=TOP_K):
    """Call a match_* RPC and return its rows."""
    resp = supabase.rpc(rpc_name, {
        "query_embedding": json.dumps(query_vec),   # pgvector text format
        "match_count": k,
    }).execute()
    return resp.data


def main():
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    for q in QUESTIONS:
        print("=" * 72)
        print("Q:", q)
        qvec = embed_one(openai_client, q)

        print("\n  Top schema matches (which tables):")
        for row in retrieve(supabase, "match_schema_chunks", qvec):
            print(f"    {row['similarity']:.3f}  {row['table_name']}")

        print("\n  Top glossary matches (what the words mean):")
        for row in retrieve(supabase, "match_glossary_chunks", qvec):
            print(f"    {row['similarity']:.3f}  {row['term']:22}  ->  {row['sql_hint'][:55]}")
        print()

    print("Validation complete. If the right tables and terms appear, Phase 1 is done.")


if __name__ == "__main__":
    main()