import json
from pathlib import Path
from typing import Any


def parse_claude_transcript(path: Path) -> dict[str, Any]:
    """Sum token usage across assistant turns in a Claude Code transcript JSONL file.

    Malformed lines are skipped rather than raised, since the transcript may still
    be open for writes by the running session when this is called near session end.
    """
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    model: str | None = None
    assistant_turns = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "assistant":
            continue
        usage = (row.get("message") or {}).get("usage")
        if not usage:
            continue
        totals["input"] += usage.get("input_tokens") or 0
        totals["output"] += usage.get("output_tokens") or 0
        totals["cache_read"] += usage.get("cache_read_input_tokens") or 0
        totals["cache_creation"] += usage.get("cache_creation_input_tokens") or 0
        model = row["message"].get("model") or model
        assistant_turns += 1
    return {**totals, "model": model, "assistant_turns": assistant_turns}
