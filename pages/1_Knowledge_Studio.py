from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.document_processing import (  # noqa: E402
    ChunkConfig,
    chunk_metrics,
    detect_pii,
    normalize_document,
    persist_and_parse_upload,
    rank_preview_chunks,
    recommend_chunk_config,
    split_document,
)
from src.ingestion import build_chunk_records, ensure_local_catalog  # noqa: E402
from src.knowledge_store import (  # noqa: E402
    archive_public_document,
    publish_document,
    update_public_document,
)
from src.local_catalog import LocalCatalog, stable_document_id  # noqa: E402
from src.local_runtime import run_command_streaming  # noqa: E402
from src.portfolio_rag import get_collections, load_embedding_model, load_settings  # noqa: E402
from src.ui import apply_streamlit_theme  # noqa: E402


DATA_DIR = ROOT / "data"
PUBLIC_PATH = DATA_DIR / "portfolio_docs.json"
CATALOG_PATH = DATA_DIR / "local_catalog.sqlite3"
ARCHIVE_PATH = DATA_DIR / "archive" / "public_docs.json"
UPLOADS = DATA_DIR / "local_uploads"


def read_public_documents() -> list[dict[str, Any]]:
    if not PUBLIC_PATH.exists():
        return []
    payload = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
    return [normalize_document(item, default_visibility="public") for item in payload]


@st.cache_data(show_spinner=False)
def parse_upload(name: str, data: bytes) -> list[dict[str, Any]]:
    return persist_and_parse_upload(name, data, UPLOADS)


@st.cache_resource(show_spinner=False)
def embedding_model():
    settings = load_settings(ROOT / ".env")
    return load_embedding_model(settings)


def catalog() -> LocalCatalog:
    return ensure_local_catalog(DATA_DIR)


def chunk_document(document: dict[str, Any], config: ChunkConfig) -> list[dict[str, Any]]:
    return split_document(document, config)


@st.cache_data(ttl=15, show_spinner=False)
def indexed_fingerprints() -> dict[str, set[str]]:
    try:
        settings = load_settings(ROOT / ".env")
        _, collection, _ = get_collections(settings)
        result: dict[str, set[str]] = {}
        for row in collection.find({}, {"doc_id": 1, "content_hash": 1}):
            result.setdefault(str(row.get("doc_id") or ""), set()).add(str(row.get("content_hash") or ""))
        return result
    except Exception:
        return {}


def index_state(item: dict[str, Any], indexed: dict[str, set[str]]) -> str:
    hashes = indexed.get(str(item.get("doc_id") or ""), set())
    if not hashes:
        return "not indexed"
    return "indexed" if item.get("content_hash") in hashes else "outdated"


def upload_tab(local_catalog: LocalCatalog) -> None:
    st.subheader("上传与智能切片")
    st.caption("原始上传文件只保存在本机；新资料默认是私有资料。")
    files = st.file_uploader(
        "上传资料",
        type=["json", "md", "txt", "csv", "docx", "pdf"],
        accept_multiple_files=True,
    )
    parsed: list[dict[str, Any]] = []
    for uploaded in files or []:
        try:
            parsed.extend(parse_upload(Path(uploaded.name).name, uploaded.getvalue()))
        except Exception as error:
            st.error(f"{uploaded.name}: {error}")
    if not parsed:
        st.info("上传文件后，这里会显示解析正文、PII 风险、智能切片建议和临时召回测试。")
        return

    selected_index = st.selectbox(
        "预览文档",
        range(len(parsed)),
        format_func=lambda index: parsed[index]["title"],
    )
    document = parsed[selected_index]
    recommended = recommend_chunk_config(document)
    mode = st.segmented_control("切片配置", ["Auto recommended", "Manual"], default="Auto recommended")
    if mode == "Manual":
        strategy = st.selectbox("切片策略", ["recursive", "markdown", "paragraph"])
        chunk_size = st.slider("Chunk size", 200, 2000, recommended.chunk_size, 50)
        overlap = st.slider("Overlap", 0, int(chunk_size * 0.25), min(recommended.chunk_overlap, int(chunk_size * 0.25)), 10)
        config = ChunkConfig(strategy, chunk_size, overlap)
    else:
        config = recommended
        st.success(
            f"推荐配置：{config.strategy} / chunk {config.chunk_size} / overlap {config.chunk_overlap}"
        )

    chunks = chunk_document(document, config)
    metrics = chunk_metrics(chunks)
    metric_columns = st.columns(5)
    metric_columns[0].metric("文档", len(parsed))
    metric_columns[1].metric("片段", metrics["count"])
    metric_columns[2].metric("平均长度", metrics["average_length"])
    metric_columns[3].metric("最短 / 最长", f"{metrics['min_length']} / {metrics['max_length']}")
    metric_columns[4].metric("过短比例", f"{metrics['too_short_ratio']:.0%}")
    for warning in metrics["warnings"]:
        st.warning(warning)

    findings = detect_pii(document["body"])
    if findings:
        kinds = ", ".join(sorted({item["type"] for item in findings}))
        st.warning(f"检测到可能的个人敏感信息：{kinds}。保存为私有资料不受影响，公开前请脱敏。")

    raw_tab, clean_tab, chunks_tab, recall_tab = st.tabs(["解析正文", "清洗正文", "切片预览", "临时召回测试"])
    with raw_tab:
        st.text_area("解析正文", document["body"], height=360, label_visibility="collapsed")
    with clean_tab:
        st.code(document["body"][:12000], language="text")
    with chunks_tab:
        for chunk in chunks:
            with st.expander(f"Chunk {chunk['chunk_index'] + 1} · {len(chunk['body'])} chars"):
                st.write(chunk["body"])
    with recall_tab:
        query = st.text_input("测试问题", placeholder="例如：Junyi 有哪些 MongoDB 项目经验？")
        if st.button("对当前预览片段运行 Top-5", disabled=not query.strip()):
            with st.spinner("正在计算当前文档片段的相似度…"):
                for rank, result in enumerate(rank_preview_chunks(chunks, query, embedding_model()), 1):
                    with st.expander(f"#{rank} · score {result['score']:.4f}", expanded=rank == 1):
                        st.write(result["body"])

    save_columns = st.columns(2)
    if save_columns[0].button("保存为本地私有资料", type="primary", use_container_width=True):
        rows = []
        active_ids = set()
        for item in parsed:
            item_config = config if item is document else recommend_chunk_config(item)
            source_name = str((item.get("metadata") or {}).get("source") or item["title"])
            enriched = {
                **item,
                "source": "manual_upload",
                "relative_path": source_name,
                "path": str(UPLOADS / source_name),
                "metadata": {
                    **(item.get("metadata") or {}),
                    "source_path": str(UPLOADS / source_name),
                    "chunking": {
                        "strategy": item_config.strategy,
                        "chunk_size": item_config.chunk_size,
                        "chunk_overlap": item_config.chunk_overlap,
                    },
                },
            }
            rows.append(enriched)
            active_ids.add(stable_document_id(enriched))
        local_catalog.upsert_documents(rows, active_ids=active_ids)
        st.success(f"已保存并启用 {len(rows)} 份私有资料。请在“索引维护”统一重建索引。")

    publish_confirm = st.checkbox("我已检查正文并完成脱敏，允许发布到公开知识库")
    pii_override = not findings or st.checkbox("正文仍含 PII；我确认这些内容可以公开")
    if save_columns[1].button(
        "发布当前文档为公开资料",
        disabled=not publish_confirm or not pii_override,
        use_container_width=True,
    ):
        public_document = {
            **document,
            "metadata": {
                **(document.get("metadata") or {}),
                "chunking": {
                    "strategy": config.strategy,
                    "chunk_size": config.chunk_size,
                    "chunk_overlap": config.chunk_overlap,
                },
            },
        }
        result = publish_document(PUBLIC_PATH, public_document)
        st.success("已发布到公开 JSON。" if result["created"] else "相同正文已存在，没有重复添加。")
        st.warning("云端 Demo 尚未同步；确认后手动运行 npm run seed:atlas。")


def private_library(local_catalog: LocalCatalog, indexed: dict[str, set[str]]) -> None:
    filter_columns = st.columns(4)
    search = filter_columns[0].text_input("搜索标题、正文或路径")
    status = filter_columns[1].selectbox("状态", ["active", "all", "discovered", "excluded", "parse_error", "needs_ocr"])
    file_type = filter_columns[2].text_input("文件类型", placeholder="docx / md / py")
    index_filter = filter_columns[3].selectbox("索引状态", ["indexed", "all", "outdated", "not indexed"])
    detail_filters = st.columns(3)
    source = detail_filters[0].text_input("来源", placeholder="resume_root / manual_upload")
    project = detail_filters[1].text_input("项目", placeholder="项目目录名")
    parse_status = detail_filters[2].selectbox("解析状态", ["all", "ready", "needs_ocr", "parse_error"])
    page = st.number_input("页码", min_value=1, value=1, step=1)
    result = local_catalog.query(
        search=search,
        filters={
            "status": status,
            "file_type": file_type,
            "source": source,
            "project": project,
            "parse_status": parse_status,
        },
        page=int(page),
        page_size=50,
    )
    rows = []
    by_id = {}
    for item in result["items"]:
        state = index_state(item, indexed)
        if index_filter != "all" and state != index_filter:
            continue
        by_id[item["doc_id"]] = item
        rows.append(
            {
                "选择": False,
                "doc_id": item["doc_id"],
                "标题": item["title"],
                "状态": item["status"],
                "来源": item["source"],
                "项目": item["project"],
                "类型": item["file_type"],
                "解析": item["parse_status"],
                "索引": state,
                "修改时间": item["modified_at"] or "",
            }
        )
    st.caption(f"共 {result['total']} 条 · 每页 50 条 · 当前第 {result['page']} / {max(1, math.ceil(result['total'] / 50))} 页")
    if not rows:
        st.info("当前筛选条件下没有资料。")
        return
    edited = st.data_editor(
        rows,
        hide_index=True,
        use_container_width=True,
        disabled=[key for key in rows[0] if key != "选择"],
        key="private-library-table",
    )
    selected_ids = [row["doc_id"] for row in edited if row["选择"]]
    actions = st.columns(3)
    if actions[0].button("启用所选", disabled=not selected_ids, use_container_width=True):
        local_catalog.set_status(selected_ids, "active")
        st.rerun()
    if actions[1].button("排除所选（不删原文件）", disabled=not selected_ids, use_container_width=True):
        local_catalog.set_status(selected_ids, "excluded")
        st.rerun()
    if actions[2].button("恢复为待选择", disabled=not selected_ids, use_container_width=True):
        local_catalog.set_status(selected_ids, "discovered")
        st.rerun()

    detail_id = st.selectbox("查看资料详情", list(by_id), format_func=lambda doc_id: by_id[doc_id]["title"])
    item = by_id[detail_id]
    detail_columns = st.columns(4)
    detail_columns[0].metric("状态", item["status"])
    detail_columns[1].metric("索引", index_state(item, indexed))
    detail_columns[2].metric("文件类型", item["file_type"] or "unknown")
    detail_columns[3].metric("大小", f"{item['size_bytes'] / 1024:.1f} KB")
    st.code(item["source_path"] or item["relative_path"] or "No source path", language="text")
    body_tab, chunks_tab, override_tab = st.tabs(["完整正文", "实际切片", "RAG 摘要与配置"])
    with body_tab:
        if item["parse_status"] == "needs_ocr":
            st.warning("OCR not enabled：图片或扫描版 PDF 暂不进入索引。")
        st.text_area("完整正文", item["body"], height=420, disabled=True, label_visibility="collapsed")
    with chunks_tab:
        config = ChunkConfig(item["chunk_strategy"], item["chunk_size"], item["chunk_overlap"])
        preview_doc = {"doc_id": item["doc_id"], "title": item["title"], "body": item["summary"] or item["body"], "visibility": "private"}
        for chunk in split_document(preview_doc, config):
            with st.expander(f"Chunk {chunk['chunk_index'] + 1} · {len(chunk['body'])} chars"):
                st.write(chunk["body"])
    with override_tab:
        summary = st.text_area("专用于 RAG 的摘要（留空则使用完整正文）", item["summary"], height=180)
        config_columns = st.columns(3)
        strategy = config_columns[0].selectbox("策略", ["recursive", "markdown", "paragraph"], index=["recursive", "markdown", "paragraph"].index(item["chunk_strategy"]), key=f"strategy-{detail_id}")
        size = config_columns[1].number_input("Chunk size", 200, 2000, item["chunk_size"], 50, key=f"size-{detail_id}")
        overlap = config_columns[2].number_input("Overlap", 0, int(size * 0.25), min(item["chunk_overlap"], int(size * 0.25)), 10, key=f"overlap-{detail_id}")
        if st.button("保存摘要与切片配置"):
            local_catalog.update_summary(detail_id, summary)
            local_catalog.update_chunking(detail_id, strategy, int(size), int(overlap))
            st.success("已保存。索引状态将在重建前显示为 outdated。")


def public_library(indexed: dict[str, set[str]]) -> None:
    documents = read_public_documents()
    search = st.text_input("搜索公开资料")
    filtered = [item for item in documents if search.lower() in (item["title"] + " " + item["body"]).lower()]
    st.caption(f"公开知识库共 {len(documents)} 条，当前显示 {len(filtered)} 条。")
    if not filtered:
        st.info("没有匹配的公开资料。")
        return
    doc_id = st.selectbox("公开资料", [item["doc_id"] for item in filtered], format_func=lambda value: next(item["title"] for item in filtered if item["doc_id"] == value))
    item = next(item for item in filtered if item["doc_id"] == doc_id)
    metadata = item.get("metadata") or {}
    with st.form("edit-public-document"):
        title = st.text_input("标题", item["title"])
        body = st.text_area("正文", item["body"], height=360)
        columns = st.columns(3)
        url = columns[0].text_input("URL", str(item.get("url") or ""))
        category = columns[1].text_input("Category", str(metadata.get("category") or ""))
        updated = columns[2].text_input("Updated", str(item.get("updated") or ""))
        if st.form_submit_button("保存公开资料", type="primary"):
            update_public_document(PUBLIC_PATH, doc_id, {"title": title, "body": body, "url": url, "category": category, "updated": updated})
            st.success("公开 JSON 已更新。本地索引和云端 Atlas 尚未同步。")
    st.caption(f"当前本地索引状态：{index_state(item, indexed)}")
    confirm = st.checkbox("确认从公开知识库移除，并保存到本地 archive")
    if st.button("归档并移除公开资料", disabled=not confirm):
        archive_public_document(PUBLIC_PATH, ARCHIVE_PATH, doc_id)
        st.rerun()


def library_tab(local_catalog: LocalCatalog) -> None:
    st.subheader("资料库")
    indexed = indexed_fingerprints()
    visibility = st.segmented_control("资料范围", ["私有资料", "公开资料"], default="私有资料")
    if visibility == "私有资料":
        private_library(local_catalog, indexed)
    else:
        public_library(indexed)


def versions_tab(local_catalog: LocalCatalog) -> None:
    st.subheader("版本与重复资料")
    st.caption("系统只推荐最新版；在你确认前，不会自动排除任何旧文件。")
    duplicates = local_catalog.exact_duplicate_groups()
    st.metric("完全重复组", len(duplicates))
    for group in duplicates[:20]:
        with st.expander(f"{group['count']} 份完全相同正文 · {group['content_hash'][:12]}"):
            for doc_id in group["doc_ids"]:
                item = local_catalog.get(doc_id)
                st.write(f"- {item['title']} · `{item['relative_path']}` · {item['status']}")
    if st.button("检测简历与上传资料的近似版本"):
        with st.spinner("正在比较候选版本…"):
            st.session_state["version_groups"] = local_catalog.detect_version_groups()
    groups = st.session_state.get("version_groups", [])
    for group in groups:
        latest_id = group["latest_doc_id"]
        latest = local_catalog.get(latest_id)
        with st.expander(f"版本组 · 推荐保留：{latest['title']}"):
            options = []
            for raw in group["documents"]:
                item = local_catalog.get(raw["doc_id"])
                options.append(item["doc_id"])
                marker = "推荐最新版" if item["doc_id"] == latest_id else "旧版本候选"
                st.write(f"**{marker}** · {item['title']} · {item['modified_at'] or 'unknown time'} · {item['status']}")
            selected = st.multiselect("选择要排除或恢复的版本", options, format_func=lambda value: local_catalog.get(value)["title"], key=f"versions-{group['group_id']}")
            columns = st.columns(3)
            if columns[0].button("排除所选", disabled=not selected, key=f"exclude-{group['group_id']}"):
                local_catalog.set_status(selected, "excluded")
                st.rerun()
            if columns[1].button("恢复所选", disabled=not selected, key=f"restore-{group['group_id']}"):
                local_catalog.set_status(selected, "active")
                st.rerun()
            confirm_latest = columns[2].checkbox("确认仅保留最新版", key=f"confirm-{group['group_id']}")
            if columns[2].button("仅保留推荐最新版", disabled=not confirm_latest, key=f"latest-{group['group_id']}"):
                local_catalog.set_status([value for value in options if value != latest_id], "excluded")
                local_catalog.set_status([latest_id], "active")
                st.rerun()


def maintenance_tab(local_catalog: LocalCatalog) -> None:
    st.subheader("索引维护")
    public_documents = read_public_documents()
    active_private = local_catalog.active_documents()
    indexed = indexed_fingerprints()
    source_documents = [*public_documents, *active_private]
    chunks = build_chunk_records(source_documents)
    current_hashes = {item["doc_id"]: item["content_hash"] for item in chunks}
    pending = sum(indexed.get(doc_id) != {content_hash} for doc_id, content_hash in current_hashes.items())
    metrics = st.columns(5)
    metrics[0].metric("公开资料", len(public_documents))
    metrics[1].metric("启用私有资料", len(active_private))
    metrics[2].metric("待索引 / 过期", pending)
    metrics[3].metric("预计 chunks", len(chunks))
    try:
        settings = load_settings(ROOT / ".env")
        metrics[4].metric("Embedding", settings.embedding_model_id.split("/")[-1])
    except Exception:
        metrics[4].metric("Embedding", "unavailable")
    if pending:
        st.warning("资料已变化，索引需要更新。你可以完成一批编辑后再统一重建。")
    else:
        st.success("SQLite / JSON 与当前 MongoDB chunks 一致。")
    if st.button("重新生成 Embedding 并重建 Vector Search Index", type="primary"):
        with st.status("正在重建本地索引…", expanded=True) as status:
            output = st.empty()
            lines: list[str] = []

            def show_line(line: str) -> None:
                lines.append(line)
                output.code("\n".join(lines[-40:]), language="text")

            return_code = run_command_streaming([sys.executable, "-u", str(ROOT / "scripts" / "ingest.py")], ROOT, show_line)
            status.update(
                label="索引构建完成" if return_code == 0 else "索引构建失败",
                state="complete" if return_code == 0 else "error",
            )
    st.divider()
    st.subheader("云端公开 Demo 同步")
    st.write("公开 JSON 修改后，本地索引与云端 Atlas 需要分别更新。云端 seed 只读取 `data/portfolio_docs.json`。")
    st.code("npm run seed:atlas", language="powershell")


st.set_page_config(page_title="Knowledge Studio", page_icon="📚", layout="wide")
apply_streamlit_theme()
st.markdown('<div class="product-kicker">LOCAL KNOWLEDGE STUDIO</div>', unsafe_allow_html=True)
st.title("知识库工作台")
st.write("浏览、筛选、更新和切片本地资料。排除资料只影响知识库，不会删除 Word、PDF、代码或项目原文件。")

try:
    local_catalog = catalog()
except Exception as error:
    st.error(f"无法打开本地资料目录：{error}")
    st.stop()

tabs = st.tabs(["Upload & Chunk", "Library", "Versions & Duplicates", "Index Maintenance"])
with tabs[0]:
    upload_tab(local_catalog)
with tabs[1]:
    library_tab(local_catalog)
with tabs[2]:
    versions_tab(local_catalog)
with tabs[3]:
    maintenance_tab(local_catalog)
