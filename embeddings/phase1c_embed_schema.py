"""
phase1c_embed_schema.py
-----------------------
Reads output/schema_raw.json, embeds each table's chunk_text with OpenAI,
and stores the vectors in the Supabase `schema_chunks` table.

Prereq: run config/supabase_setup.sql ONCE in the Supabase SQL Editor first.
"""

import json
import os

from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
SCHEMA_FILE = os.path.join("output", "schema_raw.json")


def load_chunks(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def embed_texts(openai_client, texts, batch_size=100):
    """Embed a list of texts -> list of 1536-dim vectors, order preserved."""
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        resp = openai_client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend(item.embedding for item in resp.data)
    return vectors


def to_rows(chunks, vectors):
    """Pair each chunk with its vector, formatting the embedding for pgvector."""
    rows = []
    for chunk, vec in zip(chunks, vectors):
        rows.append({
            "table_name": chunk["table_name"],
            "chunk_text": chunk["chunk_text"],
            "embedding": json.dumps(vec),   # pgvector text format: "[0.1, 0.2, ...]"
        })
    return rows


def main():
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    chunks = load_chunks(SCHEMA_FILE)
    print(f"Loaded {len(chunks)} chunks from {SCHEMA_FILE}")

    texts = [c["chunk_text"] for c in chunks]
    print(f"Embedding {len(texts)} chunks with {EMBED_MODEL}...")
    vectors = embed_texts(openai_client, texts)
    print(f"Got {len(vectors)} vectors of dimension {len(vectors[0])}")

    rows = to_rows(chunks, vectors)

    # Idempotent: clear previous rows so re-running never duplicates data.
    supabase.table("schema_chunks").delete().gt("id", 0).execute()
    supabase.table("schema_chunks").insert(rows).execute()

    print(f"Inserted {len(rows)} rows into schema_chunks. Phase 1c complete.")


if __name__ == "__main__":
    main()