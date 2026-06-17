from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import generate_answer, get_collections, load_embedding_model, load_settings  # noqa: E402


st.set_page_config(page_title="Local RAG Portfolio Assistant", page_icon="RAG", layout="centered")
st.title("Local RAG Portfolio Assistant")
st.caption("Ask questions about Junyi Chen's projects, skills, internships, and technical background.")


@st.cache_resource
def load_runtime():
    settings = load_settings(ROOT / ".env")
    _, collection, _ = get_collections(settings)
    model = load_embedding_model(settings)
    return settings, collection, model


settings, collection, model = load_runtime()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi, ask me about Junyi's projects, skills, internships, or AI/data experience.",
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

query = st.chat_input("Ask about Junyi's portfolio")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving portfolio context and generating an answer..."):
            answer = generate_answer(collection, model, settings, query)
        st.write(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
