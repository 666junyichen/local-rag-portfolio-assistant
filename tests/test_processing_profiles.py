from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from src.processing_profiles import (
    PreprocessingProfile,
    ProcessingProfile,
    profile_from_legacy,
    recommend_processing_profile,
)


def test_preprocessing_profile_is_immutable_and_has_safe_defaults() -> None:
    profile = PreprocessingProfile()

    assert profile.normalize_whitespace is True
    assert profile.remove_urls is False
    assert profile.remove_emails is False
    with pytest.raises(FrozenInstanceError):
        profile.remove_urls = True  # type: ignore[misc]


def test_processing_profile_validates_modes_and_token_bounds() -> None:
    invalid_profiles = (
        {"chunk_mode": "unknown"},
        {"parent_mode": "page"},
        {"index_mode": "fast"},
        {"profile_version": 2},
        {"profile_version": True},
        {"max_tokens": 199},
        {"max_tokens": 2001},
        {"max_tokens": 400, "overlap_tokens": -1},
        {"max_tokens": 400, "overlap_tokens": 101},
        {"parent_max_tokens": 199},
        {"child_max_tokens": 2001},
    )

    for values in invalid_profiles:
        with pytest.raises(ValueError):
            ProcessingProfile(**values)


def test_processing_profile_rejects_empty_delimiter() -> None:
    with pytest.raises(ValueError, match="delimiter"):
        ProcessingProfile(delimiter="")


@pytest.mark.parametrize("delimiter", [" ", "\n", "\n\n", "\r\n\r\n", "\t\n"])
def test_processing_profile_accepts_any_non_empty_delimiter(delimiter: str) -> None:
    assert ProcessingProfile(delimiter=delimiter).delimiter == delimiter


def test_parent_child_requires_smaller_child_budget() -> None:
    with pytest.raises(ValueError, match="child_max_tokens"):
        ProcessingProfile(
            chunk_mode="parent_child",
            max_tokens=400,
            parent_max_tokens=400,
            child_max_tokens=400,
        )


def test_parent_child_requires_one_canonical_child_budget() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        ProcessingProfile(
            chunk_mode="parent_child",
            max_tokens=200,
            child_max_tokens=180,
        )


def test_direct_parent_child_constructor_has_coherent_defaults() -> None:
    profile = ProcessingProfile(chunk_mode="parent_child")

    assert profile.max_tokens == profile.child_max_tokens == 800
    assert profile.child_max_tokens < profile.parent_max_tokens
    assert ProcessingProfile.from_dict(profile.to_dict()).digest() == profile.digest()


def test_parent_child_overlap_is_limited_by_child_budget() -> None:
    with pytest.raises(ValueError, match="child_max_tokens"):
        ProcessingProfile.parent_child(overlap_tokens=100)


def test_parent_child_factory_uses_approved_defaults() -> None:
    profile = ProcessingProfile.parent_child()

    assert profile.chunk_mode == "parent_child"
    assert profile.max_tokens == 180
    assert profile.child_max_tokens == 180
    assert profile.parent_max_tokens == 700
    assert profile.overlap_tokens == 20
    assert profile.parent_mode == "paragraph"
    assert profile.max_tokens == profile.child_max_tokens
    assert ProcessingProfile.from_dict(profile.to_dict()) == profile
    assert profile.digest() == "41211b68e5cd3d92f2b9fbd9856eafa102a1d9aa4a2995e61cd3beb4d8606c95"


def test_resume_semantic_factory_uses_approved_defaults() -> None:
    profile = ProcessingProfile.resume_semantic()

    assert profile.chunk_mode == "resume_semantic"
    assert profile.max_tokens == 320
    assert profile.overlap_tokens == 0
    assert profile.parent_mode == "semantic_section"


@pytest.mark.parametrize(
    "factory",
    [ProcessingProfile.parent_child, ProcessingProfile.resume_semantic],
)
def test_factories_reject_chunk_mode_overrides(
    factory: Callable[..., ProcessingProfile],
) -> None:
    with pytest.raises(ValueError, match="chunk_mode"):
        factory(chunk_mode="general")


def test_profile_roundtrip_and_digest_are_stable() -> None:
    profile = ProcessingProfile.parent_child(
        preprocessing=PreprocessingProfile(remove_urls=True)
    )
    payload = profile.to_dict()

    assert ProcessingProfile.from_dict(payload) == profile
    assert ProcessingProfile.from_dict(profile.to_dict()).digest() == profile.digest()
    assert profile.digest() == "f34f0284370e0b9c44ce9f847401e0e794fd158aa8de49e05cf7dd479c5e1b2f"


def test_old_resume_profile_migrates_to_resume_semantic() -> None:
    profile = profile_from_legacy(
        "Junyi Resume", "docx", "recursive", 600, 60, "tokens"
    )

    assert profile == ProcessingProfile.resume_semantic()


def test_existing_resume_semantic_legacy_strategy_maps_to_resume() -> None:
    profile = profile_from_legacy(
        "Candidate profile", "docx", "resume_semantic", 800, 80, "tokens"
    )

    assert profile == ProcessingProfile.resume_semantic()


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(True, 60), (600, True), (0, 0), (600, -1), (600, 151)],
)
def test_legacy_values_are_validated_before_resume_shortcut(
    chunk_size: int, overlap: int
) -> None:
    with pytest.raises(ValueError):
        profile_from_legacy(
            "Candidate Resume",
            "docx",
            "recursive",
            chunk_size,
            overlap,
            "tokens",
        )


def test_generic_docx_legacy_profile_does_not_migrate_as_resume() -> None:
    profile = profile_from_legacy(
        "Quarterly report", "docx", "recursive", 600, 60, "tokens"
    )

    assert profile == ProcessingProfile(max_tokens=600, overlap_tokens=60)


def test_legacy_cv_identity_migrates_known_old_profile() -> None:
    profile = profile_from_legacy(
        "Junyi CV", "docx", "recursive", 600, 60, "tokens"
    )

    assert profile == ProcessingProfile.resume_semantic()


@pytest.mark.parametrize("strategy", ["markdown", "paragraph", "recursive"])
def test_single_level_legacy_strategies_preserve_valid_token_values(strategy: str) -> None:
    profile = profile_from_legacy(
        "Project notes", "md", strategy, 640, 64, "tokens"
    )

    assert profile.chunk_mode == "general"
    assert profile.max_tokens == 640
    assert profile.overlap_tokens == 64


def test_character_legacy_values_use_conservative_four_to_one_conversion() -> None:
    # Legacy character budgets use ceil(chars / 4), then clamp to the supported
    # 200-2000 token range. This avoids overstating how much text a chunk can hold.
    profile = profile_from_legacy(
        "Project notes", "md", "markdown", 1001, 81, "characters"
    )

    assert profile.max_tokens == 251
    assert profile.overlap_tokens == 21


def test_recommendations_match_document_shape() -> None:
    resume = {
        "title": "Candidate Resume",
        "body": "Experience",
        "metadata": {"file_type": "docx"},
    }
    long_pdf = {
        "title": "Research archive",
        "body": "evidence " * 2100,
        "metadata": {"file_type": "pdf"},
    }
    long_markdown = {
        "title": "Handbook",
        "body": "section " * 2100,
        "metadata": {"file_type": "md"},
    }
    csv_document = {
        "title": "Rows",
        "body": "a,b\n1,2",
        "metadata": {"file_type": "csv"},
    }
    short_json = {
        "title": "Summary",
        "body": '{"status": "ok"}',
        "metadata": {"file_type": "json"},
    }

    assert recommend_processing_profile(resume) == ProcessingProfile.resume_semantic()
    assert recommend_processing_profile(long_pdf) == ProcessingProfile.parent_child()
    assert recommend_processing_profile(long_markdown) == ProcessingProfile.parent_child()
    assert recommend_processing_profile(csv_document) == ProcessingProfile(
        max_tokens=800, overlap_tokens=0
    )
    assert recommend_processing_profile(short_json) == ProcessingProfile(
        max_tokens=800, overlap_tokens=0
    )


def test_resume_recommendation_uses_title_and_source_identity_markers() -> None:
    cv_pdf = {
        "title": "Candidate document",
        "body": "Experience",
        "metadata": {"file_type": "pdf", "source": "uploads/Junyi-CV.pdf"},
    }
    chinese_resume = {
        "title": "个人简历",
        "body": "Experience",
        "metadata": {"file_type": "pdf", "source": "candidate.pdf"},
    }

    assert recommend_processing_profile(cv_pdf) == ProcessingProfile.resume_semantic()
    assert recommend_processing_profile(chinese_resume) == ProcessingProfile.resume_semantic()


def test_structured_files_never_auto_select_resume_semantic() -> None:
    csv_resume = {
        "title": "Candidate Resume",
        "body": "name,skill\nJunyi,Python",
        "metadata": {"file_type": "csv"},
    }
    json_resume = {
        "title": "Candidate",
        "body": '{"skill": "Python"}',
        "metadata": {"file_type": "json", "source": "master resume"},
    }

    assert recommend_processing_profile(csv_resume) == ProcessingProfile(
        max_tokens=800, overlap_tokens=0
    )
    assert recommend_processing_profile(json_resume) == ProcessingProfile(
        max_tokens=800, overlap_tokens=0
    )


@pytest.mark.parametrize("source", ["master resume", "resume-parser"])
def test_generic_resume_source_label_is_not_a_filename_marker(source: str) -> None:
    document = {
        "title": "README",
        "body": "Short ordinary markdown.",
        "metadata": {"file_type": "md", "source": source},
    }

    assert recommend_processing_profile(document) == ProcessingProfile()


@pytest.mark.parametrize(
    "document",
    [
        {
            "title": "Résumé",
            "body": "Experience",
            "metadata": {"file_type": "pdf"},
        },
        {
            "title": "Curriculum Vitae",
            "body": "Experience",
            "metadata": {"file_type": "pdf"},
        },
        {
            "title": "Candidate",
            "body": "Experience",
            "file_name": "Junyi-CV.pdf",
            "metadata": {"file_type": "pdf"},
        },
        {
            "title": "README",
            "body": "Experience",
            "metadata": {"source": "resume_root", "file_type": "md"},
        },
        {
            "title": "README",
            "body": "Experience",
            "source_root": "resume_root",
            "metadata": {"file_type": "md"},
        },
    ],
)
def test_resume_recommendation_recognizes_normalized_identity_markers(
    document: dict[str, object],
) -> None:
    assert recommend_processing_profile(document) == ProcessingProfile.resume_semantic()


@pytest.mark.parametrize(
    "source",
    [
        "projects/resume-parser/README.md",
        "archives/curriculum-vitae/notes.md",
        "uploads/mycv.pdf",
    ],
)
def test_resume_recommendation_ignores_directory_and_partial_markers(
    source: str,
) -> None:
    document = {
        "title": "README",
        "body": "Short ordinary document.",
        "metadata": {"source": source},
    }

    assert recommend_processing_profile(document) == ProcessingProfile()


def test_generic_docx_recommendation_depends_on_document_length() -> None:
    short_docx = {
        "title": "Quarterly report",
        "body": "Short ordinary document.",
        "metadata": {"file_type": "docx", "source": "quarterly-report.docx"},
    }
    long_docx = {
        "title": "Operations handbook",
        "body": "procedure " * 2100,
        "metadata": {"file_type": "docx", "source": "operations-handbook.docx"},
    }

    assert recommend_processing_profile(short_docx) == ProcessingProfile()
    assert recommend_processing_profile(long_docx) == ProcessingProfile.parent_child()


def test_file_type_inference_skips_candidates_without_suffixes() -> None:
    document = {
        "title": "Rows",
        "body": "a,b\n1,2",
        "path": "uploads/rows.csv",
        "metadata": {"source": "manual upload"},
    }

    assert recommend_processing_profile(document) == ProcessingProfile(
        max_tokens=800, overlap_tokens=0
    )


def test_token_estimate_groups_accented_and_cyrillic_words() -> None:
    document = {
        "title": "International notes",
        "body": "développeur разработчик " * 900,
        "metadata": {"file_type": "pdf"},
    }

    assert recommend_processing_profile(document) == ProcessingProfile()


@pytest.mark.parametrize("character", ["한", "あ", "カ", "ก"])
def test_script_run_estimate_stays_below_long_document_threshold(
    character: str,
) -> None:
    document = {
        "title": "Language notes",
        "body": character * 3900,
        "metadata": {"file_type": "pdf"},
    }

    assert recommend_processing_profile(document) == ProcessingProfile()


@pytest.mark.parametrize("character", ["한", "あ", "カ", "ก"])
def test_script_run_estimate_crosses_long_document_threshold(
    character: str,
) -> None:
    document = {
        "title": "Language notes",
        "body": character * 4100,
        "metadata": {"file_type": "pdf"},
    }

    assert recommend_processing_profile(document) == ProcessingProfile.parent_child()
