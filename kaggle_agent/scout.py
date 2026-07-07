from __future__ import annotations

from typing import Any


def slug_from_ref(ref: str) -> str:
    return ref.rstrip("/").split("/")[-1]


def build_scout_item(row: dict[str, Any], group: str, source_index: int) -> dict[str, Any]:
    ref = str(row.get("ref") or row.get("url") or "")
    slug = slug_from_ref(ref) if ref else str(row.get("slug") or "")
    return {
        "slug": slug,
        "group": group,
        "source_index": source_index,
        "agent_decision": "pending",
        "agent_notes": "",
        "raw": row,
    }
