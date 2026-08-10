from __future__ import annotations

import unittest

from src.space_migration import (
    add_text_space_filter,
    add_vector_space_filter,
    migrate_collection_spaces,
)


class SpaceMigrationTests(unittest.TestCase):
    def test_index_definitions_gain_space_filter_idempotently(self) -> None:
        vector, changed = add_vector_space_filter(
            {"fields": [{"type": "vector", "path": "embedding"}]}
        )
        vector_again, changed_again = add_vector_space_filter(vector)
        text, text_changed = add_text_space_filter(
            {"mappings": {"fields": {"body": {"type": "string"}}}}
        )

        self.assertTrue(changed)
        self.assertFalse(changed_again)
        self.assertEqual(vector_again, vector)
        self.assertEqual(vector["fields"][-1], {"type": "filter", "path": "space_id"})
        self.assertTrue(text_changed)
        self.assertEqual(text["mappings"]["fields"]["space_id"], {"type": "token"})

    def test_migration_updates_chunks_and_existing_indexes_without_embeddings(self) -> None:
        class Result:
            modified_count = 12

        class Collection:
            def __init__(self):
                self.updated = []
                self.dropped = []
                self.created = []

            def update_many(self, query, update):
                self.query = query
                self.update = update
                return Result()

            def list_search_indexes(self):
                return [
                    {
                        "name": "vector",
                        "type": "vectorSearch",
                        "status": "READY",
                        "latestDefinition": {
                            "fields": [{"type": "vector", "path": "embedding"}]
                        },
                    },
                    {
                        "name": "text",
                        "type": "search",
                        "status": "READY",
                        "latestDefinition": {
                            "mappings": {"fields": {"body": {"type": "string"}}}
                        },
                    },
                ]

            def update_search_index(self, name, definition):
                self.updated.append((name, definition))

            def drop_search_index(self, name):
                self.dropped.append(name)

            def create_search_index(self, model):
                self.created.append(model.document)

        collection = Collection()
        result = migrate_collection_spaces(
            collection,
            vector_index_name="vector",
            text_index_name="text",
            wait_seconds=0,
        )

        self.assertEqual(result["migrated_chunks"], 12)
        self.assertEqual(result["updated_indexes"], ["vector", "text"])
        self.assertEqual(collection.update["$set"]["space_id"], "portfolio")
        self.assertEqual(
            [name for name, _definition in collection.updated],
            ["text"],
        )
        self.assertEqual(collection.dropped, ["vector"])
        self.assertEqual(
            collection.created[0]["type"],
            "vectorSearch",
        )
        self.assertIn(
            {"type": "filter", "path": "space_id"},
            collection.created[0]["definition"]["fields"],
        )


if __name__ == "__main__":
    unittest.main()

