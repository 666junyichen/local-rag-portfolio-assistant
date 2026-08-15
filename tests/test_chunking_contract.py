import json

from scripts.export_chunking_contract import EXPECTED_PATH, build_contract


def test_local_chunking_matches_the_checked_in_cross_runtime_contract() -> None:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert build_contract() == expected


def test_docx_resume_fixture_keeps_each_semantic_section_separate() -> None:
    contract = build_contract()["cases"]["resume-docx"]
    assert [parent["section_type"] for parent in contract["parents"]] == [
        "profile",
        "education",
        "project",
        "project",
        "internship",
    ]
