"""
pipeline.py
-----------
The fully integrated NL->SQL pipeline.

answer_question(): question -> SQL -> validate -> execute (+ self-correct, + learn)
respond():         answer_question() -> plain-English answer (THE entry point)
"""

from retrieval import get_clients, save_query
from generate_sql import generate_sql
from execute import is_safe_select, run_sql
from answer import summarize, to_text_table


def answer_question(openai_client, supabase, question, max_attempts=3, learn=True):
    feedback = None
    last_sql = None

    for attempt in range(1, max_attempts + 1):
        sql = generate_sql(openai_client, supabase, question, feedback=feedback)
        last_sql = sql

        safe, reason = is_safe_select(sql)
        if not safe:
            feedback = f"The query was rejected: {reason} Return ONE read-only SELECT."
            continue

        try:
            columns, rows = run_sql(sql)
        except Exception as e:
            feedback = f"PREVIOUS SQL:\n{sql}\n\nDATABASE ERROR:\n{e}"
            continue

        if learn:
            try:
                save_query(openai_client, supabase, question, sql)
            except Exception:
                pass

        return {"ok": True, "sql": sql, "columns": columns,
                "rows": rows, "attempts": attempt}

    return {"ok": False, "sql": last_sql,
            "error": f"Failed after {max_attempts} attempts.", "attempts": max_attempts}


def respond(openai_client, supabase, question):
    """Full round-trip: question -> {plain-English answer, SQL, table, rows}."""
    result = answer_question(openai_client, supabase, question)

    if not result["ok"]:
        return {
            "ok": False,
            "answer": "I wasn't able to generate a working query for that question.",
            "sql": result.get("sql"),
            "table": None,
            "attempts": result["attempts"],
        }

    answer_text = summarize(openai_client, question, result["columns"], result["rows"])
    return {
        "ok": True,
        "answer": answer_text,
        "sql": result["sql"],
        "table": to_text_table(result["columns"], result["rows"]),
        "columns": result["columns"], 
        "rows": result["rows"],
        "attempts": result["attempts"],
    }


def main():
    openai_client, supabase = get_clients()
    questions = [
        "How many Phase 3 cancer trials are currently recruiting?",
        "Show me 5 trials that were terminated early, with the reason.",
        "How many trials does each sponsor agency class have? Top 5.",
    ]
    for q in questions:
        print("=" * 72)
        print("Q:", q)
        r = respond(openai_client, supabase, q)
        print("\nANSWER:", r["answer"])
        print("\nSQL (attempt " + str(r["attempts"]) + "):\n", r["sql"])
        if r["table"]:
            print("\nData:\n" + r["table"])
        print()


if __name__ == "__main__":
    main()