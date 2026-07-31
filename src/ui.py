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
    body = source.get("body") or source.get("snippet") or ""
    st.markdown(f"**{title}** · `{category}` · score `{score:.3f}`")
    st.caption(body[:320] + ("…" if len(body) > 320 else ""))

