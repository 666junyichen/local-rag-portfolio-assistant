from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import (  # noqa: E402
    generate_answer_with_sources,
    get_collections,
    load_embedding_model,
    load_settings,
    retrieve_for_question,
    try_load_reranker,
    vector_search,
)
from src.evaluation import evaluate_rankings, load_benchmark  # noqa: E402
from src.query_planning import should_refuse_without_retrieval  # noqa: E402
from src.streamlit_spaces import local_catalog, render_space_selector  # noqa: E402
from src.ui import apply_streamlit_theme, render_source  # noqa: E402

EVAL_PATH = ROOT / "data" / "local_eval_questions.json"
BENCHMARK_PATH = ROOT / "evals" / "rag_benchmark.json"

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
    space_ids = render_space_selector(
        local_catalog(ROOT / "data"),
        key_prefix="lab",
    )
    use_threshold = st.toggle("启用 score threshold", value=False)
    threshold = st.slider("Threshold", 0.0, 1.0, 0.55, 0.01, key="lab_threshold", disabled=not use_threshold)
    scope = st.radio("资料范围", ["public", "all"], key="lab_scope", format_func=lambda value: "仅公开" if value == "public" else "公开 + 私有")
    mode = st.selectbox(
        "Retrieval mode",
        ["adaptive", "baseline", "full-text", "hybrid", "hybrid-rerank"],
        format_func=lambda value: {
            "adaptive": "Adaptive / 智能路由",
            "baseline": "Vector / 向量检索",
            "full-text": "BM25 / 全文检索",
            "hybrid": "Hybrid / RRF 融合",
            "hybrid-rerank": "Hybrid + Cross-Encoder Rerank",
        }[value],
        help="Vector 使用语义向量；全文检索使用 BM25；Hybrid 使用 BM25 + Vector + RRF；Rerank 再加入本地 Cross-Encoder。",
    )

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
        reranker, reranker_warning = (
            try_load_reranker(settings) if mode == "hybrid-rerank" else (None, None)
        )
        if reranker_warning:
            st.warning(
                "Cross-Encoder 暂时不可用，已自动回退到 hybrid 检索。"
                f"\n\n降级原因：{reranker_warning}"
            )
        started = time.perf_counter()
        diagnostics: dict = {}
        if mode == "adaptive":
            results = retrieve_for_question(
                collection,
                model,
                settings,
                query,
                top_k=top_k,
                score_threshold=threshold if use_threshold else None,
                scope=scope,
                retrieval_mode="adaptive",
                diagnostics=diagnostics,
                space_ids=space_ids,
            )
        else:
            results = vector_search(
                collection,
                model,
                settings,
                query,
                top_k=top_k,
                score_threshold=threshold if use_threshold else None,
                scope=scope,
                mode="hybrid" if mode == "hybrid-rerank" else mode,
                reranker=reranker,
                space_ids=space_ids,
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        channel_counts: dict[str, int] = {}
        for result in results:
            for channel in result.get("retrieval_channels", []):
                channel_counts[channel] = channel_counts.get(channel, 0) + 1
        st.caption(
            f"模式：{mode} · 召回渠道：{channel_counts or {'vector': len(results)}} · "
            f"延迟：{elapsed_ms:.0f} ms"
        )
        if mode == "adaptive":
            st.caption(
                f"Actual path: {diagnostics.get('retrieval_path', 'vector')} · "
                f"Reranker: {'used' if diagnostics.get('reranker_triggered') else 'not used'} · "
                f"Reason: {', '.join(diagnostics.get('reranker_reasons', [])) or 'fast-path'}"
            )
            if diagnostics.get("fallback_reason"):
                st.warning(f"Adaptive fallback: {diagnostics['fallback_reason']}")
        st.caption("结果会展示 Vector/BM25 排名、RRF 融合分数和 rerank 前后变化。")
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
                reranker=reranker,
                retrieval_mode="hybrid" if mode == "hybrid-rerank" else mode,
                force_reranker=mode == "hybrid-rerank",
                space_ids=space_ids,
            )
            st.write(answer)
    except Exception as error:
        st.error(f"Retrieval failed: {error}")

st.divider()
st.subheader("批量评测 / Benchmark")
st.caption("使用固定的 50 条中英文标注问题计算 hit、recall、MRR、nDCG、隐私隔离和延迟。")
if st.button("运行当前模式评测", use_container_width=True):
    try:
        settings, collection, model = runtime()
        reranker, reranker_warning = (
            try_load_reranker(settings) if mode == "hybrid-rerank" else (None, None)
        )
        if reranker_warning:
            st.warning(
                "Cross-Encoder 暂时不可用，本次评测已自动回退到 hybrid。"
                f"\n\n降级原因：{reranker_warning}"
            )
        cases = load_benchmark(BENCHMARK_PATH)
        rankings = {}
        latencies = {}
        progress = st.progress(0, text="Preparing benchmark...")
        for index, case in enumerate(cases, 1):
            started = time.perf_counter()
            if should_refuse_without_retrieval(case.question):
                rankings[case.case_id] = []
            elif mode == "adaptive":
                rankings[case.case_id] = retrieve_for_question(
                    collection,
                    model,
                    settings,
                    case.question,
                    top_k=10,
                    scope=case.scope,
                    retrieval_mode="adaptive",
                    space_ids=space_ids,
                )
            else:
                rankings[case.case_id] = vector_search(
                    collection,
                    model,
                    settings,
                    case.question,
                    top_k=10,
                    scope=case.scope,
                    mode="hybrid" if mode == "hybrid-rerank" else mode,
                    reranker=reranker,
                    space_ids=space_ids,
                )
            latencies[case.case_id] = (time.perf_counter() - started) * 1000
            progress.progress(index / len(cases), text=f"{index}/{len(cases)} · {case.case_id}")
        report = {"mode": mode, **evaluate_rankings(cases, rankings, ks=(1, 3, 5, 10), latencies_ms=latencies)}
        report_path = ROOT / "evals" / f"latest-report-{mode}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"评测完成，报告保存在 {report_path.name}")
        st.json(report)
    except Exception as error:
        st.error(f"Benchmark failed: {error}")

