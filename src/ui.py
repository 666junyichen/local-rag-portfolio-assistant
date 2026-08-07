from __future__ import annotations

from typing import Any

import streamlit as st


def apply_streamlit_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
        [data-testid="stSidebar"] {border-right: 1px solid #dfe4ec; background: #f8fafc;}
        h1, h2, h3 {letter-spacing: 0; color: #172033;}
        .product-kicker {color: #296dff; font-size: .76rem; font-weight: 750; letter-spacing: .08em;}
        .stButton > button {border-radius: 6px; min-height: 2.65rem; border-color: #d7deea;}
        .stButton > button:hover {border-color: #296dff; color: #175cd3;}
        [data-testid="stChatMessage"] {border: 1px solid #e1e6ee; border-radius: 8px; padding: .85rem 1rem;}
        [data-testid="stStatusWidget"] {border-radius: 6px;}
        code {color: #175cd3;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_source(source: dict[str, Any]) -> None:
    metadata = source.get("metadata") or {}
    title = source.get("title") or "Untitled"
    category = metadata.get("category") or source.get("category") or "portfolio"
    score = float(source.get("score") or 0)
    body = source.get("raw_body") or source.get("body") or source.get("snippet") or ""
    channels = source.get("retrieval_channels") or source.get("retrievalChannels") or []
    channel_label = "+".join(channels) if channels else "vector"
    fusion = source.get("fusion_score") or source.get("fusionScore")
    reranker = source.get("reranker_score")
    diagnostics = [f"score `{score:.3f}`", f"channel `{channel_label}`"]
    if source.get("vector_rank") is not None:
        diagnostics.append(f"vector rank `{int(source['vector_rank'])}`")
    if source.get("bm25_rank") is not None:
        diagnostics.append(f"BM25 rank `{int(source['bm25_rank'])}`")
    if fusion is not None:
        diagnostics.append(f"RRF `{float(fusion):.4f}`")
    if reranker is not None:
        diagnostics.append(f"reranker `{float(reranker):.3f}`")
    st.markdown(f"**{title}** · `{category}` · " + " · ".join(diagnostics))
    st.caption(body[:320] + ("…" if len(body) > 320 else ""))
