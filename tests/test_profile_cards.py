from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.profile_cards import format_profile_context, load_profile_cards


class ProfileCardTests(unittest.TestCase):
    def test_public_scope_filters_private_facts_and_keeps_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profile.json"
            path.write_text(json.dumps([
                {"fact_id": "public", "label": "Role", "value": "AI application engineer", "visibility": "public", "source_doc_ids": ["doc_1"]},
                {"fact_id": "private", "label": "Phone", "value": "secret", "visibility": "private", "source_doc_ids": ["doc_2"]},
            ]), encoding="utf-8")
            cards = load_profile_cards(path, scope="public")
        self.assertEqual([card["fact_id"] for card in cards], ["public"])
        self.assertIn("source: doc_1", format_profile_context(cards))

    def test_invalid_card_without_sources_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profile.json"
            path.write_text(json.dumps([{"fact_id": "bad", "label": "Role", "value": "Developer"}]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profile_cards(path)


if __name__ == "__main__":
    unittest.main()
