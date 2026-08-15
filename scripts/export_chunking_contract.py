from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.hierarchical_chunking import ChunkHierarchy, build_chunk_hierarchy
from src.processing_profiles import ProcessingProfile


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "chunking"
CASES_PATH = FIXTURE_ROOT / "cases.json"
EXPECTED_PATH = FIXTURE_ROOT / "expected.json"


def _profile(name: str) -> ProcessingProfile:
    if name == "general":
        return ProcessingProfile()
    if name == "parent_child":
        return ProcessingProfile.parent_child()
    if name == "resume_semantic":
        return ProcessingProfile.resume_semantic()
    raise ValueError(f"Unsupported processing profile: {name}")


def _normalize(hierarchy: ChunkHierarchy) -> dict[str, Any]:
    parent_indexes = {
        parent.chunk_id: index for index, parent in enumerate(hierarchy.parents)
    }
    group_indexes: dict[str, int] = {}

    def group_index(group_id: str) -> int:
        if group_id not in group_indexes:
            group_indexes[group_id] = len(group_indexes)
        return group_indexes[group_id]

    def values(chunk: Any) -> dict[str, Any]:
        return {
            "raw_body": chunk.raw_body,
            "section_type": chunk.section_type,
            "section_path": chunk.section_path,
            "entity_title": chunk.entity_title,
            "token_count": chunk.token_count,
            "retrieval_priority": chunk.retrieval_priority,
            "semantic_group_index": group_index(chunk.semantic_group_id),
        }

    return {
        "parents": [values(parent) for parent in hierarchy.parents],
        "children": [
            {
                **values(child),
                "parent_index": parent_indexes[child.parent_chunk_id],
            }
            for child in hierarchy.children
        ],
    }


def build_contract() -> dict[str, Any]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    output: dict[str, Any] = {"schema_version": 1, "cases": {}}
    for case in cases:
        body = (FIXTURE_ROOT / case["file"]).read_text(encoding="utf-8")
        hierarchy = build_chunk_hierarchy(
            {
                "doc_id": f"fixture-{case['case_id']}",
                "title": case["title"],
                "body": body,
                "visibility": "public",
                "metadata": {"file_type": case["source_format"]},
            },
            _profile(case["profile"]),
        )
        output["cases"][case["case_id"]] = _normalize(hierarchy)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_contract(), ensure_ascii=False, indent=2) + "\n"
    if args.write:
        EXPECTED_PATH.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
