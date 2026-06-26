"""
retrieval.py
------------
Shared RAG retrieval layer (extracted now that a third consumer - the SQL
generator - needs it; the "rule of three" for when to abstract).

Embeds a question and pulls the most relevant schema + glossary context
from the two Supabase vector stores.
"""

import json
import os

from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"


def get_clients():
    """Build the OpenAI and Supabase clients from environment variables."""
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return openai_client, supabase


def embed_one(openai_client, text):
    """Embed a single string -> one 1536-dim vector."""
    resp = openai_client.embeddings.create(model=EMBED_MODEL, input=[text])
    return resp.data[0].embedding


def _retrieve(supabase, rpc_name, query_vec, k):
    resp = supabase.rpc(rpc_name, {
        "query_embedding": json.dumps(query_vec),
        "match_count": k,
    }).execute()
    return resp.data


def retrieve_context(openai_client, supabase, question,
                     n_schema=8, n_glossary=6, n_examples=3):
    """Return (schema_rows, glossary_rows, example_rows) for a question."""
    qvec = embed_one(openai_client, question)
    schema_rows = _retrieve(supabase, "match_schema_chunks", qvec, n_schema)
    glossary_rows = _retrieve(supabase, "match_glossary_chunks", qvec, n_glossary)
    example_rows = _retrieve(supabase, "match_query_history", qvec, n_examples)
    return schema_rows, glossary_rows, example_rows

def save_query(openai_client, supabase, question, sql):
    """Persist a successful (question -> working SQL) pair for future few-shot use."""
    vec = embed_one(openai_client, question)
    supabase.table("query_history").insert({
        "question": question,
        "sql_text": sql,
        "embedding": json.dumps(vec),
    }).execute()