from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from scripts import ingest


class IngestScriptTests(unittest.TestCase):
    @patch("scripts.ingest.create_text_index")
    @patch("scripts.ingest.create_vector_index")
    @patch("scripts.ingest.load_embedding_model")
    @patch("scripts.ingest.get_collections")
    @patch("scripts.ingest.load_knowledge_documents", return_value=[])
    def test_empty_knowledge_base_keeps_indexes_without_inserting_documents(
        self,
        _load_documents: MagicMock,
        get_collections: MagicMock,
        load_model: MagicMock,
        create_vector: MagicMock,
        create_text: MagicMock,
    ) -> None:
        settings = MagicMock(
            embedding_model_id="test-model",
            vector_index_name="vector_index",
            text_index_name="text_index",
        )
        collection = MagicMock()
        history = MagicMock()
        get_collections.return_value = (MagicMock(), collection, history)
        model = MagicMock()
        model.encode_query.return_value.shape = (1, 384)
        load_model.return_value = model

        with patch("scripts.ingest.load_settings", return_value=settings):
            ingest.main()

        collection.delete_many.assert_called_once_with({})
        collection.insert_many.assert_not_called()
        create_vector.assert_called_once()
        create_text.assert_called_once()


if __name__ == "__main__":
    unittest.main()
