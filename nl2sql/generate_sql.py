"""
generate_sql.py
---------------
Phase 2: turn a natural-language question into executable PostgreSQL.

Pipeline:
    question
      -> retrieve schema + glossary context (retrieval.py)
      -> assemble a prompt (system rules + retrieved context + question)
      -> GPT-4 writes SQL
      -> extract clean SQL
"""

import os
import re

from dotenv import load_dotenv

from retrieval import get_clients, retrieve_context  # sibling module

load_dotenv()

CHAT_MODEL = "gpt-4o"   # swap for gpt-4-turbo, gpt-4.1, or a Claude model later

# The model's job description + guardrails. This is STABLE across all questions.
SYSTEM_PROMPT = """You are an expert PostgreSQL analyst for the AACT clinical-trials database.

Follow these rules strictly:
- Use ONLY the tables and columns given in the context. NEVER invent table or column names.
- All trial data is in the `ctgov` schema; every related table joins to `studies` on nct_id.
- Return exactly ONE read-only SELECT statement. Never write INSERT, UPDATE, DELETE, DROP, or ALTER.
- Translate business terms using the provided glossary SQL conditions verbatim.
- If the query JOINs tables that can produce duplicate rows per trial, COUNT(DISTINCT studies.nct_id) instead of COUNT(*).
- Output ONLY the raw SQL. No explanation, no comments, no markdown code fences.
"""


def build_user_prompt(question, schema_rows, glossary_rows, example_rows=None, feedback=None):
    schema_block = "\n".join(f"- {r['chunk_text']}" for r in schema_rows)
    glossary_block = "\n".join(
        f"- \"{r['term']}\" means: {r['sql_hint']}" for r in glossary_rows
    )
    prompt = (
        f"RELEVANT TABLES:\n{schema_block}\n\n"
        f"RELEVANT BUSINESS-TERM -> SQL MAPPINGS:\n{glossary_block}\n\n"
    )
    if example_rows:
        ex_block = "\n\n".join(
            f"Q: {e['question']}\nSQL: {e['sql_text']}" for e in example_rows
        )
        prompt += f"EXAMPLES OF CORRECT QUERIES (follow their style and exact literals):\n{ex_block}\n\n"
    prompt += f"QUESTION: {question}\n\n"
    if feedback:
        prompt += ("YOUR PREVIOUS ATTEMPT FAILED. Fix it based on this error:\n"
                   f"{feedback}\n\n")
    prompt += "Write one PostgreSQL SELECT query that answers the question."
    return prompt


def extract_sql(text):
    """Strip markdown fences if the model added them despite instructions."""
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE)
    return text.strip()


def generate_sql(openai_client, supabase, question, feedback=None):
    schema_rows, glossary_rows, example_rows = retrieve_context(openai_client, supabase, question)
    user_prompt = build_user_prompt( question, schema_rows, glossary_rows, example_rows, feedback)
    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,   
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=500,
    )
    return extract_sql(resp.choices[0].message.content)


def main():
    openai_client, supabase = get_clients()
    questions = [
        "How many Phase 3 cancer trials are currently recruiting?",
        "Which industry-sponsored diabetes trials were completed recently?",
        "Show me trials that were terminated early.",
    ]
    for q in questions:
        print("=" * 72)
        print("Q:", q)
        sql = generate_sql(openai_client, supabase, q)
        print("\nGenerated SQL:\n")
        print(sql)
        print()


if __name__ == "__main__":
    main()