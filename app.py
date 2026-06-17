from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import generate_answer, get_collections, load_embedding_model, load_settings  # noqa: E402


EXAMPLE_QUESTIONS = [
    "What are Junyi Chen's strongest AI and data projects?",
    "What MongoDB experience does Junyi have?",
    "Summarize Junyi for a full-stack role.",
    "Which projects show LLM or AI application experience?",
]

DEMO_QUERY_MAP = {
    "ai_projects": EXAMPLE_QUESTIONS[0],
    "mongodb": EXAMPLE_QUESTIONS[1],
    "full_stack": EXAMPLE_QUESTIONS[2],
    "llm": EXAMPLE_QUESTIONS[3],
}


st.set_page_config(page_title="Local RAG Portfolio Assistant", page_icon="R", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1120px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(49, 51, 63, 0.12);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 0.94rem;
        line-height: 1.45;
    }
    .hero-eyebrow {
        color: #517065;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .hero-title {
        font-size: clamp(2.1rem, 4vw, 3.65rem);
        font-weight: 760;
        line-height: 0.98;
        margin: 0;
    }
    .hero-copy {
        color: #4a4f59;
        font-size: 1.05rem;
        line-height: 1.62;
        max-width: 760px;
        margin-top: 1rem;
    }
    .local-note {
        background: #f7f3e8;
        border: 1px solid #e7dac1;
        border-radius: 8px;
        color: #4b4232;
        padding: 0.85rem 1rem;
        margin: 1rem 0 1.2rem;
    }
    .source-note {
        color: #626976;
        font-size: 0.92rem;
        margin-top: 0.45rem;
    }
    .stButton > button {
        border-radius: 8px;
        min-height: 2.5rem;
        justify-content: center;
    }
    .example-card {
        min-height: 4.1rem;
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 8px;
        background: #f7f8fb;
        padding: 0.9rem 1rem;
        color: #202634;
        font-weight: 650;
        line-height: 1.35;
        display: flex;
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="hero-eyebrow">Private local RAG demo</div>', unsafe_allow_html=True)
st.markdown('<h1 class="hero-title">Local RAG Portfolio Assistant</h1>', unsafe_allow_html=True)
st.markdown(
    """
    <p class="hero-copy">
    Ask questions about Junyi Chen's projects, skills, internships, and technical background.
    The assistant retrieves curated portfolio facts from MongoDB Vector Search, then answers with a
    local Ollama-hosted Gemma model.
    </p>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="local-note">Local-only demo. Requires MongoDB Local Atlas, Ollama, and the model configured in <code>.env</code>.</div>',
    unsafe_allow_html=True,
)


@st.cache_resource
def load_runtime():
    settings = load_settings(ROOT / ".env")
    _, collection, _ = get_collections(settings)
    model = load_embedding_model(settings)
    return settings, collection, model


settings, collection, model = load_runtime()

with st.sidebar:
    st.header("Demo Stack")
    st.markdown(
        """
        - MongoDB Vector Search
        - `voyageai/voyage-4-nano`
        - Ollama Gemma
        - Streamlit
        """
    )
    st.divider()
    st.subheader("Runtime")
    st.caption("Configured from local `.env`")
    st.code(
        f"DB: {settings.db_name}\n"
        f"Collection: {settings.collection_name}\n"
        f"LLM: {settings.ollama_model}\n"
        f"Embedding: {settings.embedding_model_id}",
        language="text",
    )
    st.divider()
    st.subheader("Knowledge Base")
    st.markdown("Answers are based on `data/portfolio_docs.json`.")
    st.caption("Only curated, resume-safe portfolio summaries are included.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi, ask me about Junyi's projects, skills, internships, or AI/data experience.",
        }
    ]

demo_key = st.query_params.get("demo")
if demo_key and not st.session_state.get(f"demo_loaded_{demo_key}"):
    demo_question = DEMO_QUERY_MAP.get(demo_key)
    if demo_question:
        st.session_state.pending_query = demo_question
        st.session_state[f"demo_loaded_{demo_key}"] = True

st.subheader("Try a Portfolio Question")
example_cols = st.columns(2)
for index, question in enumerate(EXAMPLE_QUESTIONS):
    with example_cols[index % 2]:
        st.markdown(f'<div class="example-card">{question}</div>', unsafe_allow_html=True)
        if st.button("Ask this", key=f"example_{index}", use_container_width=True):
            st.session_state.pending_query = question

st.markdown(
    '<p class="source-note">Source: curated local knowledge base in <code>data/portfolio_docs.json</code>.</p>',
    unsafe_allow_html=True,
)
st.divider()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

query = st.session_state.pop("pending_query", None)
typed_query = st.chat_input("Ask about Junyi's portfolio")
if typed_query:
    query = typed_query

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving portfolio context and generating an answer..."):
            answer = generate_answer(collection, model, settings, query)
        st.write(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
