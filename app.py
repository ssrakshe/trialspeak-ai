"""
app.py
------
Streamlit chat UI for the Clinical NL->SQL system.
Run with:  streamlit run app.py
"""

import sys
import pathlib

# Put the nl2sql package dir on the path so its sibling imports resolve.
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "nl2sql"))

import os
import streamlit as st

# Bridge hosted secrets (e.g. Streamlit Community Cloud) into env vars, so the
# imported modules' os.getenv(...) calls work in deployment. Local dev uses .env.
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass  # no secrets.toml locally - load_dotenv() handles .env instead

from pipeline import respond
from retrieval import get_clients


# Build the OpenAI + Supabase clients ONCE and reuse them across reruns.
@st.cache_resource
def load_clients():
    return get_clients()


st.set_page_config(page_title="TrialSpeak AI", page_icon="🔬", layout="centered")
st.title("🔬 TrialSpeak AI")
st.caption("Ask 500,000+ clinical trials anything — in plain English. No SQL required.")

openai_client, supabase = load_clients()

# Sample questions to help a first-time user.
with st.sidebar:
    st.subheader("Try asking")
    for s in [
        "How many Phase 3 cancer trials are currently recruiting?",
        "How many trials does each sponsor agency class have? Top 5.",
        "Show me 5 trials that were terminated early, with the reason.",
    ]:
        st.markdown(f"- {s}")

# Conversation history lives in session state (per browser session).
if "messages" not in st.session_state:
    st.session_state.messages = []


def render_details(msg):
    """The expandable 'view SQL and data' panel for an assistant message."""
    if not msg.get("sql"):
        return
    with st.expander("View SQL and data"):
        st.code(msg["sql"], language="sql")
        if msg.get("rows"):
            st.dataframe(
                [dict(zip(msg["columns"], row)) for row in msg["rows"]],
                use_container_width=True,
            )


# Replay the existing conversation.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_details(msg)

# The input box at the bottom.
question = st.chat_input("e.g. How many recruiting trials are there?")
if question:
    # Show and store the user's message.
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Generate and show the assistant's answer.
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            r = respond(openai_client, supabase, question)
        st.markdown(r["answer"])
        assistant_msg = {
            "role": "assistant",
            "content": r["answer"],
            "sql": r.get("sql"),
            "columns": r.get("columns"),
            "rows": r.get("rows"),
        }
        render_details(assistant_msg)

    st.session_state.messages.append(assistant_msg)