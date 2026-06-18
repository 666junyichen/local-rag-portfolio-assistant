from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import generate_answer, get_collections, load_embedding_model, load_settings  # noqa: E402


EXAMPLE_QUESTIONS = {
    "zh": [
        "Junyi Chen 最强的 AI 和数据项目有哪些？",
        "Junyi 有哪些 MongoDB 相关经验？",
        "请用中文总结 Junyi 为什么适合全栈开发岗位。",
        "哪些项目体现了 Junyi 的 LLM 或 AI 应用能力？",
    ],
    "en": [
        "What are Junyi Chen's strongest AI and data projects?",
        "What MongoDB experience does Junyi have?",
        "Summarize Junyi for a full-stack role.",
        "Which projects show LLM or AI application experience?",
    ],
}

COPY = {
    "zh": {
        "eyebrow": "私有本地 RAG demo",
        "title": "Local RAG Portfolio Assistant",
        "hero": (
            "用中文或英文询问 Junyi Chen 的项目、技能、实习和技术背景。"
            "系统会从 MongoDB Vector Search 检索精选 portfolio 信息，再用本地 Ollama Gemma 模型生成回答。"
        ),
        "local_note": "本地运行 demo。需要 MongoDB Local Atlas、Ollama，以及 .env 中配置的模型。",
        "stack": "技术栈",
        "runtime": "运行配置",
        "runtime_caption": "来自本地 .env",
        "knowledge": "知识库",
        "knowledge_text": "回答基于 data/portfolio_docs.json。",
        "knowledge_caption": "只包含适合公开展示、适合简历使用的精选摘要。",
        "try_question": "试试这些中文问题",
        "ask_this": "问这个",
        "source": "来源：本地精选知识库 data/portfolio_docs.json。",
        "greeting": "你好，可以用中文问我 Junyi 的项目、技能、实习、AI/data 经验或全栈能力。",
        "chat_input": "用中文询问 Junyi 的 portfolio",
        "spinner": "正在检索 portfolio 上下文并生成回答...",
        "language_label": "界面语言",
    },
    "en": {
        "eyebrow": "Private local RAG demo",
        "title": "Local RAG Portfolio Assistant",
        "hero": (
            "Ask questions about Junyi Chen's projects, skills, internships, and technical background. "
            "The assistant retrieves curated portfolio facts from MongoDB Vector Search, then answers with a local Ollama-hosted Gemma model."
        ),
        "local_note": "Local-only demo. Requires MongoDB Local Atlas, Ollama, and the model configured in .env.",
        "stack": "Demo Stack",
        "runtime": "Runtime",
        "runtime_caption": "Configured from local .env",
        "knowledge": "Knowledge Base",
        "knowledge_text": "Answers are based on data/portfolio_docs.json.",
        "knowledge_caption": "Only curated, resume-safe portfolio summaries are included.",
        "try_question": "Try a Portfolio Question",
        "ask_this": "Ask this",
        "source": "Source: curated local knowledge base in data/portfolio_docs.json.",
        "greeting": "Hi, ask me about Junyi's projects, skills, internships, or AI/data experience.",
        "chat_input": "Ask about Junyi's portfolio",
        "spinner": "Retrieving portfolio context and generating an answer...",
        "language_label": "Interface language",
    },
}

DEMO_QUERY_MAP = {
    "ai_projects": EXAMPLE_QUESTIONS["zh"][0],
    "mongodb": EXAMPLE_QUESTIONS["zh"][1],
    "full_stack": EXAMPLE_QUESTIONS["zh"][2],
    "llm": EXAMPLE_QUESTIONS["zh"][3],
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

if "language" not in st.session_state:
    st.session_state.language = "zh"

language = st.radio(
    COPY[st.session_state.language]["language_label"],
    ["zh", "en"],
    index=0 if st.session_state.language == "zh" else 1,
    format_func=lambda value: "中文" if value == "zh" else "English",
    horizontal=True,
)
if language != st.session_state.language:
    st.session_state.language = language
    st.session_state.messages = [{"role": "assistant", "content": COPY[language]["greeting"]}]
    st.rerun()

text = COPY[language]

st.markdown(f'<div class="hero-eyebrow">{text["eyebrow"]}</div>', unsafe_allow_html=True)
st.markdown(f'<h1 class="hero-title">{text["title"]}</h1>', unsafe_allow_html=True)
st.markdown(f'<p class="hero-copy">{text["hero"]}</p>', unsafe_allow_html=True)
st.markdown(f'<div class="local-note">{text["local_note"]}</div>', unsafe_allow_html=True)


@st.cache_resource
def load_runtime():
    settings = load_settings(ROOT / ".env")
    _, collection, _ = get_collections(settings)
    model = load_embedding_model(settings)
    return settings, collection, model


settings, collection, model = load_runtime()

with st.sidebar:
    st.header(text["stack"])
    st.markdown(
        """
        - MongoDB Vector Search
        - `voyageai/voyage-4-nano`
        - Ollama Gemma
        - Streamlit
        """
    )
    st.divider()
    st.subheader(text["runtime"])
    st.caption(text["runtime_caption"])
    st.code(
        f"DB: {settings.db_name}\n"
        f"Collection: {settings.collection_name}\n"
        f"LLM: {settings.ollama_model}\n"
        f"Embedding: {settings.embedding_model_id}",
        language="text",
    )
    st.divider()
    st.subheader(text["knowledge"])
    st.markdown(text["knowledge_text"])
    st.caption(text["knowledge_caption"])

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": text["greeting"]}]

demo_key = st.query_params.get("demo")
if demo_key and not st.session_state.get(f"demo_loaded_{demo_key}"):
    demo_question = DEMO_QUERY_MAP.get(demo_key)
    if demo_question:
        st.session_state.pending_query = demo_question
        st.session_state[f"demo_loaded_{demo_key}"] = True

st.subheader(text["try_question"])
example_cols = st.columns(2)
for index, question in enumerate(EXAMPLE_QUESTIONS[language]):
    with example_cols[index % 2]:
        st.markdown(f'<div class="example-card">{question}</div>', unsafe_allow_html=True)
        if st.button(text["ask_this"], key=f"example_{language}_{index}", use_container_width=True):
            st.session_state.pending_query = question

st.markdown(f'<p class="source-note">{text["source"]}</p>', unsafe_allow_html=True)
st.divider()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

query = st.session_state.pop("pending_query", None)
typed_query = st.chat_input(text["chat_input"])
if typed_query:
    query = typed_query

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        with st.spinner(text["spinner"]):
            answer = generate_answer(collection, model, settings, query)
        st.write(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
