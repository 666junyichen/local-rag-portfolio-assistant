from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import load_reranker  # noqa: E402


PAGES = (
    ROOT / "app.py",
    ROOT / "pages" / "1_Knowledge_Studio.py",
    ROOT / "pages" / "2_Retrieval_Lab.py",
)


def main() -> int:
    if not callable(load_reranker):
        raise TypeError("src.portfolio_rag.load_reranker is not callable")

    for page in PAGES:
        app = AppTest.from_file(str(page), default_timeout=60).run()
        exceptions = list(app.exception)
        if exceptions:
            messages = "; ".join(str(error.value) for error in exceptions)
            raise RuntimeError(f"{page.name} failed to render: {messages}")
        print(f"[OK] {page.relative_to(ROOT)}")

    retrieval_lab = AppTest.from_file(
        str(ROOT / "pages" / "2_Retrieval_Lab.py"),
        default_timeout=60,
    ).run()
    mode_select = next(
        item for item in retrieval_lab.selectbox if item.label == "Retrieval mode"
    )
    expected_modes = [
        "Adaptive / 智能路由",
        "Vector / 向量检索",
        "BM25 / 全文检索",
        "Hybrid / RRF 融合",
        "Hybrid + Cross-Encoder Rerank",
    ]
    if list(mode_select.options) != expected_modes:
        raise RuntimeError(
            f"Retrieval Lab modes are {list(mode_select.options)!r}, expected {expected_modes!r}"
        )
    print("[OK] Retrieval Lab exposes adaptive, vector, full-text, hybrid, and hybrid-rerank")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
