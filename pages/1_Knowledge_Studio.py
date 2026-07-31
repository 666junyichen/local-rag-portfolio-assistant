from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.document_processing import ChunkConfig, parse_uploaded_file, split_document  # noqa: E402
from src.knowledge_store import publish_document, remove_document, save_private_documents  # noqa: E402
from src.ui import apply_streamlit_theme  # noqa: E402

PUBLIC_PATH = ROOT / "data" / "portfolio_docs.json"
PRIVATE_PATH = ROOT / "data" / "local_private_docs.json"
UPLOADS = ROOT / "data" / "local_uploads"

st.set_page_config(page_title="Knowledge Studio", page_icon="K", layout="wide")
apply_streamlit_theme()
st.markdown('<div class="product-kicker">LOCAL KNOWLEDGE STUDIO</div>', unsafe_allow_html=True)
st.title("知识库工作台")
st.write("导入、清洗和预览资料。新资料默认保持私有，只有确认脱敏后才允许发布到公开知识库。")

left, right = st.columns([0.42, 0.58], gap="large")
with left:
    files = st.file_uploader(
        "上传资料",
        type=["json", "md", "txt", "csv", "docx", "pdf"],
        accept_multiple_files=True,
    )
    strategy = st.selectbox("切片策略", ["recursive", "markdown", "paragraph"])
    chunk_size = st.slider("Chunk size", 200, 2000, 800, 50)
    overlap = st.slider("Overlap", 0, int(chunk_size * 0.25), min(80, int(chunk_size * 0.25)), 10)
    st.caption("支持 JSON、Markdown、TXT、CSV、DOCX、PDF。原始上传只保存在本机且不会进入 Git。")

parsed = []
if files:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    for uploaded in files:
        safe_name = Path(uploaded.name).name
        target = UPLOADS / safe_name
        target.write_bytes(uploaded.getvalue())
        try:
            parsed.extend(parse_uploaded_file(target))
        except Exception as error:
            st.error(f"{safe_name}: {error}")

with right:
    if parsed:
        chunks = [chunk for document in parsed for chunk in split_document(document, ChunkConfig(strategy, chunk_size, overlap))]
        lengths = [len(chunk["body"]) for chunk in chunks]
        st.metric("解析文档", len(parsed))
        metric_cols = st.columns(3)
        metric_cols[0].metric("片段数", len(chunks))
        metric_cols[1].metric("平均长度", round(sum(lengths) / len(lengths)) if lengths else 0)
        metric_cols[2].metric("重复状态", "保存时去重")
        selected = st.selectbox("预览文档", range(len(parsed)), format_func=lambda i: parsed[i]["title"])
        document = parsed[selected]
        st.caption(f"来源：{document['metadata'].get('source', 'upload')} · 字符：{len(document['body'])} · 默认：private")
        raw_tab, clean_tab, chunk_tab = st.tabs(["解析文本", "清洗文本", "切片预览"])
        with raw_tab:
            st.text_area("Parsed", document["body"], height=260, label_visibility="collapsed")
        with clean_tab:
            st.code(document["body"][:5000], language="text")
        with chunk_tab:
            for chunk in split_document(document, ChunkConfig(strategy, chunk_size, overlap)):
                with st.expander(f"Chunk {chunk['chunk_index'] + 1} · {len(chunk['body'])} chars"):
                    st.write(chunk["body"])
        action_a, action_b = st.columns(2)
        if action_a.button("保存为本地私有资料", type="primary", use_container_width=True):
            saved = save_private_documents(PRIVATE_PATH, parsed)
            st.success(f"已保存，共 {len(saved)} 条私有资料。")
        confirmed = st.checkbox("我已检查并脱敏，允许公开发布")
        if action_b.button("发布到公开知识库", disabled=not confirmed, use_container_width=True):
            created = sum(bool(publish_document(PUBLIC_PATH, item)["created"]) for item in parsed)
            st.success(f"已新增 {created} 条公开资料。请重新构建索引。")
    else:
        st.info("上传文件后，这里会显示解析结果、字符统计和切片预览。")

st.divider()
st.subheader("本地索引维护")
if st.button("重新生成 Embedding 并重建 Vector Search Index", type="primary"):
    with st.status("正在重建本地索引…", expanded=True) as status:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "ingest.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        st.code((result.stdout + "\n" + result.stderr).strip(), language="text")
        status.update(label="索引构建完成" if result.returncode == 0 else "索引构建失败", state="complete" if result.returncode == 0 else "error")

st.subheader("已登记资料")
for path, visibility in [(PUBLIC_PATH, "public"), (PRIVATE_PATH, "private")]:
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    with st.expander(f"{visibility.title()} · {len(rows)}"):
        for row in rows:
            doc_id = row.get("doc_id")
            cols = st.columns([0.78, 0.22])
            cols[0].write(f"**{row.get('title', 'Untitled')}**  \n`{doc_id or 'legacy id generated on ingestion'}`")
            if doc_id and cols[1].button("删除", key=f"delete-{visibility}-{doc_id}"):
                remove_document(path, doc_id, default_visibility=visibility)
                st.rerun()

