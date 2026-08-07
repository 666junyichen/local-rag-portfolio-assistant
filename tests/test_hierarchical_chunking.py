from __future__ import annotations

from src.document_processing import normalize_document
from src.hierarchical_chunking import build_chunk_hierarchy
from src.processing_profiles import ProcessingProfile


def test_parent_child_indexes_children_and_links_parent_evidence() -> None:
    body = "\n\n".join(
        f"## Section {index}\n" + (f"Evidence {index} about MongoDB and RAG. " * 90)
        for index in range(4)
    )
    document = normalize_document(
        {"title": "Long guide", "body": body, "visibility": "private"}
    )

    result = build_chunk_hierarchy(document, ProcessingProfile.parent_child())

    assert result.parents
    assert result.children
    parent_ids = {parent.chunk_id for parent in result.parents}
    assert all(child.parent_chunk_id in parent_ids for child in result.children)
    assert all(child.token_count <= 180 for child in result.children)
    assert all(parent.token_count <= 700 for parent in result.parents)
    assert all(child.parent_body for child in result.children)


def test_resume_semantic_parents_do_not_cross_top_level_sections() -> None:
    document = normalize_document(
        {
            "title": "Junyi Resume",
            "body": (
                "Education\n\n"
                "University of Sydney | Master of Data Science | 2025-2026\n\n"
                "Relevant courses: machine learning and data mining.\n\n"
                "Projects\n\n"
                "Local RAG Portfolio Assistant | GitHub / Demo | 2026\n\n"
                "Tech stack: Python, MongoDB, Ollama.\n\n"
                "Built local vector and full-text retrieval with source evidence."
            ),
            "metadata": {"file_type": "docx"},
            "visibility": "private",
        }
    )

    result = build_chunk_hierarchy(document, ProcessingProfile.resume_semantic())

    assert any(parent.section_type == "education" for parent in result.parents)
    assert any(parent.section_type == "project" for parent in result.parents)
    assert not any(
        "Education" in parent.raw_body and "Projects" in parent.raw_body
        for parent in result.parents
    )


def test_general_mode_keeps_parent_and_child_evidence_identical() -> None:
    document = normalize_document(
        {"title": "Short note", "body": "One focused paragraph.", "visibility": "public"}
    )

    result = build_chunk_hierarchy(document, ProcessingProfile())

    assert len(result.parents) == len(result.children) == 1
    assert result.children[0].parent_chunk_id == result.parents[0].chunk_id
    assert result.children[0].raw_body == result.parents[0].raw_body
