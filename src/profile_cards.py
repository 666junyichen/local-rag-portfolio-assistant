from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_profile_cards(path: Path, *, scope: str = "all") -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("profile cards must be a JSON array")
    cards: list[dict[str, Any]] = []
    for raw in payload:
        card = dict(raw)
        required = ("fact_id", "label", "value", "source_doc_ids")
        if any(not card.get(key) for key in required):
            raise ValueError("each profile fact requires fact_id, label, value, and source_doc_ids")
        visibility = str(card.get("visibility") or "private")
        if visibility not in {"public", "private"}:
            raise ValueError("profile fact visibility must be public or private")
        if scope == "public" and visibility != "public":
            continue
        card["visibility"] = visibility
        cards.append(card)
    return cards


def format_profile_context(cards: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- {card['label']}: {card['value']} "
        f"(source: {', '.join(str(value) for value in card['source_doc_ids'])}; "
        f"updated: {card.get('updated_at', 'unknown')})"
        for card in cards
    )
