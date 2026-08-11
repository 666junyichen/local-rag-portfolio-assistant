from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.local_catalog import LocalCatalog


def local_catalog(data_dir: Path) -> LocalCatalog:
    return LocalCatalog(data_dir / "local_catalog.sqlite3")


def render_space_selector(
    catalog: LocalCatalog,
    *,
    key_prefix: str,
    allow_cross_space: bool = True,
) -> tuple[str, ...]:
    spaces = catalog.list_spaces(include_archived=False)
    if not spaces:
        return ("portfolio",)
    if len(spaces) == 1:
        return (str(spaces[0]["space_id"]),)
    names = {str(space["space_id"]): str(space["name"]) for space in spaces}
    options = list(names)
    cross_space = False
    if allow_cross_space:
        cross_space = st.toggle(
            "跨空间查询 / Cross-space query",
            value=False,
            key=f"{key_prefix}_cross_space",
        )
    if cross_space:
        selected = st.multiselect(
            "知识空间 / Knowledge spaces",
            options,
            default=["portfolio"] if "portfolio" in options else options[:1],
            max_selections=5,
            format_func=lambda space_id: names[space_id],
            key=f"{key_prefix}_spaces",
        )
        return tuple(selected or (["portfolio"] if "portfolio" in options else options[:1]))
    selected = st.selectbox(
        "知识空间 / Knowledge space",
        options,
        index=options.index("portfolio") if "portfolio" in options else 0,
        format_func=lambda space_id: names[space_id],
        key=f"{key_prefix}_space",
    )
    return (str(selected),)
