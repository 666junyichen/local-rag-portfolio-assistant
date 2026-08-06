from __future__ import annotations

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


def test_parent_child_requires_smaller_child_budget() -> None:
    with pytest.raises(ValueError, match="child_max_tokens"):
        ProcessingProfile(
            chunk_mode="parent_child",
            parent_max_tokens=400,
            child_max_tokens=400,
        )


def test_parent_child_factory_uses_approved_defaults() -> None:
    profile = ProcessingProfile.parent_child()

    assert profile.chunk_mode == "parent_child"
    assert profile.child_max_tokens == 180
    assert profile.parent_max_tokens == 700
    assert profile.overlap_tokens == 20
    assert profile.parent_mode == "paragraph"


def test_resume_semantic_factory_uses_approved_defaults() -> None:
    profile = ProcessingProfile.resume_semantic()

    assert profile.chunk_mode == "resume_semantic"
    assert profile.max_tokens == 320
    assert profile.overlap_tokens == 0
    assert profile.parent_mode == "semantic_section"


def test_profile_roundtrip_and_digest_are_stable() -> None:
    profile = ProcessingProfile.parent_child(
        preprocessing=PreprocessingProfile(remove_urls=True)
    )
    payload = profile.to_dict()

    assert ProcessingProfile.from_dict(payload) == profile
    assert ProcessingProfile.from_dict(profile.to_dict()).digest() == profile.digest()
    assert profile.digest() == "ddebc81b769ad6bf99f6845effb6d53180fbbfc4399e6d7d945b3faf8119df28"


def test_old_resume_profile_migrates_to_resume_semantic() -> None:
    profile = profile_from_legacy(
        "Junyi Resume", "docx", "recursive", 600, 60, "tokens"
    )

    assert profile == ProcessingProfile.resume_semantic()


@pytest.mark.parametrize("strategy", ["resume_semantic", "recursive"])
def test_resume_semantic_legacy_strategy_or_docx_type_maps_to_resume(strategy: str) -> None:
    profile = profile_from_legacy(
        "Candidate profile", "docx", strategy, 800, 80, "tokens"
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
        "title": "Candidate",
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
