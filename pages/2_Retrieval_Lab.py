from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import (  # noqa: E402
    generate_answer_with_sources,
    get_collections,
    load_embedding_model,
    load_settings,
    vector_search,
)
from src.ui import apply_streamlit_theme, render_source  # noqa: E402

EVAL_PATH = ROOT / "data" / "local_eval_questions.json"

st.set_page_config(page_title="Retrieval Lab", page_icon="R", layout="wide")
apply_streamlit_theme()
st.markdown('<div class="product-kicker">RETRIEVAL EVALUATION</div>', unsafe_allow_html=True)
st.title("召回测试实验室")
st.write("观察 Top-K、相关度阈值和资料范围如何改变最终上下文。")


@st.cache_resource
def runtime():
    settings = load_settings(ROOT / ".env")
    _, collection, _ = get_collections(settings)
    return settings, collection, load_embedding_model(settings)


with st.sidebar:
    if st.button("重置参数", use_container_width=True):
        for key in ["lab_top_k", "lab_threshold", "lab_scope"]:
            st.session_state.pop(key, None)
        st.rerun()
    top_k = st.slider("Top-K", 1, 10, 5, key="lab_top_k")
    use_threshold = st.toggle("启用 score threshold", value=False)
    threshold = st.slider("Threshold", 0.0, 1.0, 0.55, 0.01, key="lab_threshold", disabled=not use_threshold)
    scope = st.radio("资料范围", ["public", "all"], key="lab_scope", format_func=lambda value: "仅公开" if value == "public" else "公开 + 私有")

saved_questions = json.loads(EVAL_PATH.read_text(encoding="utf-8")) if EVAL_PATH.exists() else []
query = st.text_input("测试问题", value=st.session_state.get("lab_query", "Junyi 有哪些 RAG 和 MongoDB 项目经验？"))
actions = st.columns([0.2, 0.2, 0.6])
run = actions[0].button("运行召回", type="primary", use_container_width=True)
generate = actions[1].button("召回并生成", use_container_width=True)
if actions[2].button("保存为固定评测问题") and query not in saved_questions:
    saved_questions.append(query)
    EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVAL_PATH.write_text(json.dumps(saved_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    st.success("已保存到本地评测集。")

if saved_questions:
    chosen = st.selectbox("固定评测问题", [""] + saved_questions)
    if chosen and st.button("载入问题"):
        st.session_state.lab_query = chosen
        st.rerun()

if run or generate:
    try:
        settings, collection, model = runtime()
        results = vector_search(
            collection,
            model,
            settings,
            query,
            top_k=top_k,
            score_threshold=threshold if use_threshold else None,
            scope=scope,
        )
        st.subheader(f"候选与入选上下文 · {len(results)}")
        if not results:
            st.warning("当前参数下没有合格资料，系统不会调用 Ollama 猜测答案。")
        for result in results:
            render_source(result)
            st.divider()
        if generate:
            st.subheader("生成答案")
            answer, _ = generate_answer_with_sources(
                collection,
                model,
                settings,
                query,
                top_k=top_k,
                score_threshold=threshold if use_threshold else None,
                scope=scope,
            )
            st.write(answer)
    except Exception as error:
        st.error(f"Retrieval failed: {error}")

