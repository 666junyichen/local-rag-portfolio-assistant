from __future__ import annotations

import time
from typing import Any

from pymongo.operations import SearchIndexModel


def add_vector_space_filter(definition: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    fields = list(definition.get("fields") or [])
    if any(field.get("path") == "space_id" for field in fields):
        return definition, False
    return {**definition, "fields": [*fields, {"type": "filter", "path": "space_id"}]}, True


def add_text_space_filter(definition: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    mappings = dict(definition.get("mappings") or {})
    fields = dict(mappings.get("fields") or {})
    if "space_id" in fields:
        return definition, False
    fields["space_id"] = {"type": "token"}
    return {**definition, "mappings": {**mappings, "fields": fields}}, True


def migrate_collection_spaces(
    collection: Any,
    *,
    vector_index_name: str,
    text_index_name: str,
    wait_seconds: int = 180,
) -> dict[str, Any]:
    result = collection.update_many(
        {"space_id": {"$exists": False}},
        {
            "$set": {
                "space_id": "portfolio",
                "space_name": "Portfolio",
                "metadata.space_id": "portfolio",
                "metadata.space_name": "Portfolio",
            }
        },
    )
    indexes = list(collection.list_search_indexes())
    updated_indexes: list[str] = []
    for index in indexes:
        name = str(index.get("name") or "")
        definition = dict(index.get("latestDefinition") or index.get("definition") or {})
        if name == vector_index_name:
            updated, changed = add_vector_space_filter(definition)
        elif name == text_index_name:
            updated, changed = add_text_space_filter(definition)
        else:
            continue
        if changed:
            if name == vector_index_name:
                collection.drop_search_index(name)
                collection.create_search_index(
                    SearchIndexModel(
                        definition=updated,
                        name=name,
                        type="vectorSearch",
                    )
                )
            else:
                collection.update_search_index(name, updated)
            updated_indexes.append(name)

    if updated_indexes and wait_seconds > 0:
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            states = {
                str(index.get("name")): str(index.get("status") or "")
                for index in collection.list_search_indexes()
            }
            if all(states.get(name) == "READY" for name in updated_indexes):
                break
            time.sleep(2)

    return {
        "migrated_chunks": int(result.modified_count),
        "updated_indexes": updated_indexes,
    }

