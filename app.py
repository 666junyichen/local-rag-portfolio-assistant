from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import (  # noqa: E402
    clear_reranker_cache,
    generate_answer_with_sources,
    get_collections,
    load_embedding_model,
    load_settings,
    store_message,
    try_load_reranker,
)
from src.local_runtime import ServiceStatus, check_ollama, check_search_index  # noqa: E402
from src.ui import apply_streamlit_theme, render_source  # noqa: E402


COPY = {
    "zh": {
        "title": "Portfolio RAG Assistant",
        "intro": "基于精选公开资料与本地私有资料，检索 Junyi Chen 的项目、技能与经历。回答会展示实际召回来源。",
        "input": "用中文询问项目、技能、实习或 AI 经验",
        "thinking": "正在检索知识库并生成回答...",
        "scope": "检索范围",
        "public": "仅公开资料",
        "all": "公开 + 私有资料",
        "settings": "检索设置",
        "threshold": "启用最低相关度",
        "sources": "检索来源",
        "local": "本地私有模式",
        "empty": "你好，可以问我关于 Junyi 的项目、技术栈、实习和求职方向。",
    },
    "en": {
        "title": "Portfolio RAG Assistant",
        "intro": "Retrieve Junyi Chen's projects, skills, and experience from curated public and local private evidence. Every answer exposes its retrieved sources.",
        "input": "Ask about projects, skills, internships, or AI experience",
        "thinking": "Retrieving evidence and generating an answer...",
        "scope": "Retrieval scope",
        "public": "Public only",
        "all": "Public + private",
        "settings": "Retrieval settings",
        "threshold": "Use minimum relevance",
        "sources": "Retrieved sources",
        "local": "Local private mode",
        "empty": "Hi. Ask me about Junyi's projects, technical stack, internships, or target roles.",
    },
}

QUESTIONS = {
    "zh": [
        "Junyi 最有代表性的 AI 和数据项目有哪些？",
        "Junyi 有哪些 MongoDB 相关经验？",
        "为什么 Junyi 适合全栈开发岗位？",
        "哪些项目体现了 LLM 或 RAG 应用能力？",
    ],
    "en": [
        "What are Junyi's strongest AI and data projects?",
        "What MongoDB experience does Junyi have?",
        "Why is Junyi a strong fit for a full-stack role?",
        "Which projects demonstrate LLM or RAG experience?",
    ],
}

st.set_page_config(page_title="Portfolio RAG Assistant", page_icon="R", layout="wide")
apply_streamlit_theme()


@st.cache_resource
def load_database(settings):
    return get_collections(settings)


@st.cache_resource
def load_embeddings(settings):
    return load_embedding_model(settings)


@st.cache_resource
def load_precision_reranker(settings):
    return try_load_reranker(settings)


if "language" not in st.session_state:
    st.session_state.language = "zh"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

language = st.session_state.language
text = COPY[language]

with st.sidebar:
    st.markdown("### Local RAG")
    if st.button("重新加载本地配置 / Reload local configuration", use_container_width=True):
        st.cache_resource.clear()
        clear_reranker_cache()
        st.rerun()
    selected_language = st.segmented_control(
        "Language / 语言",
        ["zh", "en"],
        default=language,
        format_func=lambda value: "中文" if value == "zh" else "English",
    )
    if selected_language and selected_language != language:
        st.session_state.language = selected_language
        st.rerun()
    st.caption("MongoDB Local Atlas + SentenceTransformers + Ollama")
    st.divider()
    st.markdown(f"#### {text['settings']}")
    scope_label = st.radio(text["scope"], [text["public"], text["all"]])
    scope = "public" if scope_label == text["public"] else "all"
    top_k = st.slider("Top-K", 1, 10, 5)
    use_threshold = st.toggle(text["threshold"], value=False)
    threshold = st.slider("Score threshold", 0.0, 1.0, 0.55, 0.01, disabled=not use_threshold)
    use_reranker = st.toggle(
        "高精度 reranker / High precision",
        value=False,
        help="更准确但会增加约 1–2 秒本地检索延迟；首次使用需要下载模型。",
    )
    st.divider()
    st.info(f"{text['local']}\n\n`data/portfolio_docs.json` + ignored private documents")

st.markdown('<div class="product-kicker">LOCAL KNOWLEDGE ASSISTANT</div>', unsafe_allow_html=True)
st.title(text["title"])
st.write(text["intro"])

question_cols = st.columns(2)
settings = collection = history_collection = model = None
runtime_errors: list[str] = []
runtime_details: list[str] = []
runtime_statuses: list[tuple[str, ServiceStatus]] = [
    ("Phase A feature version", ServiceStatus(True, "complete")),
    ("Streamlit UI", ServiceStatus(True, "running")),
]

try:
    settings = load_settings(ROOT / ".env")
    runtime_statuses.append(("Local configuration", ServiceStatus(True, "loaded from project .env")))
except Exception as error:
    runtime_errors.append(f"Configuration: {error}")
    runtime_statuses.append(("Local configuration", ServiceStatus(False, str(error))))

if settings:
    try:
        _, collection, history_collection = load_database(settings)
        runtime_details.append(f"MongoDB: connected to {settings.collection_name}")
        runtime_statuses.append(("MongoDB", ServiceStatus(True, "connected")))
        vector_status = check_search_index(collection, settings.vector_index_name, "Vector index")
        text_status = check_search_index(collection, settings.text_index_name, "BM25 index")
        runtime_statuses.extend(
            [("Vector index", vector_status), ("BM25 index", text_status)]
        )
        if not vector_status.available:
            runtime_errors.append(vector_status.detail)
    except Exception as error:
        runtime_errors.append(f"MongoDB: {error}")
        runtime_statuses.append(("MongoDB", ServiceStatus(False, str(error))))

    if collection is not None:
        try:
            model = load_embeddings(settings)
            runtime_details.append(f"Embedding: {settings.embedding_model_id}")
            runtime_statuses.append(("Embedding model", ServiceStatus(True, "loaded locally")))
        except Exception as error:
            runtime_errors.append(f"Embedding: {error}")
            runtime_statuses.append(("Embedding model", ServiceStatus(False, str(error))))
    else:
        runtime_details.append("Embedding: waiting for MongoDB before loading")

    ollama = check_ollama(settings.ollama_base_url, settings.ollama_model)
    if ollama.available:
        runtime_details.append(ollama.detail)
    else:
        runtime_errors.append(ollama.detail)
    runtime_statuses.append(("Ollama and model", ollama))

with st.expander("Local runtime diagnostics", expanded=bool(runtime_errors)):
    for label, status in runtime_statuses:
        marker = "✅" if status.available else "❌"
        st.write(f"{marker} **{label}**: {status.detail}")
    st.caption(
        "Local mode checks only LOCAL_MONGODB_URI, OLLAMA_BASE_URL, and OLLAMA_MODEL. "
        "Cloud credentials are never displayed or used for private documents."
    )

runtime_ready = not runtime_errors and all(
    value is not None for value in (settings, collection, history_collection, model)
)
if runtime_ready:
    st.success("Local runtime ready · " + " · ".join(runtime_details), icon="✅")
else:
    st.error("Local runtime is not ready. The page remains available for diagnostics.")
    for error in runtime_errors:
        st.write(f"- {error}")
    st.caption("Open Docker Desktop, then run the one-command local startup script:")
    st.code("powershell -ExecutionPolicy Bypass -File .\\scripts\\start-local.ps1", language="powershell")

for index, question in enumerate(QUESTIONS[language]):
    with question_cols[index % 2]:
        if st.button(
            question,
            key=f"question-{language}-{index}",
            use_container_width=True,
            disabled=not runtime_ready,
        ):
            st.session_state.pending_query = question

if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write(text["empty"])

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("sources"):
            with st.expander(f"{text['sources']} · {len(message['sources'])}"):
                for source in message["sources"]:
                    render_source(source)

query = st.session_state.pop("pending_query", None) or st.chat_input(
    text["input"], disabled=not runtime_ready
)
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    store_message(history_collection, st.session_state.session_id, "user", query)
    with st.chat_message("user"):
        st.write(query)
    with st.chat_message("assistant"):
        with st.spinner(text["thinking"]):
            retrieval_diagnostics: dict = {}
            reranker, reranker_warning = (
                load_precision_reranker(settings) if use_reranker else (None, None)
            )
            if reranker_warning:
                st.warning(
                    "Cross-Encoder 暂时不可用，已自动回退到 hybrid 检索。"
                    f"\n\n详细信息：{reranker_warning}"
                )
            answer, sources = generate_answer_with_sources(
                collection,
                model,
                settings,
                query,
                top_k=top_k,
                score_threshold=threshold if use_threshold else None,
                scope=scope,
                reranker=reranker,
                retrieval_mode="adaptive",
                force_reranker=use_reranker,
                diagnostics=retrieval_diagnostics,
            )
        path = retrieval_diagnostics.get("retrieval_path", "vector")
        reasons = ", ".join(retrieval_diagnostics.get("reranker_reasons", [])) or "fast-path"
        st.caption(
            f"Retrieval path: {path} · Reranker: "
            f"{'used' if retrieval_diagnostics.get('reranker_triggered') else 'not used'} · "
            f"Reason: {reasons} · Latency: {retrieval_diagnostics.get('latency_ms', 0):.0f} ms"
        )
        if retrieval_diagnostics.get("fallback_reason"):
            st.warning(
                "Precision reranker was unavailable; Vector results were used. "
                f"Reason: {retrieval_diagnostics['fallback_reason']}"
            )
        st.write(answer)
        if sources:
            with st.expander(f"{text['sources']} · {len(sources)}", expanded=True):
                for source in sources:
                    render_source(source)
    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
    store_message(history_collection, st.session_state.session_id, "assistant", answer)

