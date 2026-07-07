import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import STATE_DIR


FAILURE_CLASSES = {
    "transient_cli",
    "environment",
    "missing_file",
    "schema",
    "code",
    "oom",
    "timeout",
    "quota",
    "metric_mismatch",
    "rule_risk",
    "unknown",
}

REQUIRED_FIELDS = {
    "experiments.json": ["competition_slug", "experiment_key", "hypothesis"],
    "runs.json": ["run_id", "competition_slug"],
    "submissions.json": ["submission_ref", "competition_slug"],
}


def read_json(name: str, default: Any) -> Any:
    path = STATE_DIR / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, value: Any) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(name: str, value: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_list(name: str) -> list[dict[str, Any]]:
    value = read_json(name, [])
    if not isinstance(value, list):
        raise ValueError(f"{name} must contain a JSON list")
    return value


def upsert_by_key(name: str, key: str, item: dict[str, Any]) -> dict[str, Any]:
    rows = read_list(name)
    now = utc_now()
    item = dict(item)
    item.setdefault("created_at", now)
    item["updated_at"] = now
    for idx, row in enumerate(rows):
        if row.get(key) == item.get(key):
            merged = {**row, **item, "created_at": row.get("created_at", item["created_at"])}
            rows[idx] = merged
            write_json(name, rows)
            return merged
    rows.append(item)
    write_json(name, rows)
    return item


def update_matching(name: str, predicate: Any, changes: dict[str, Any]) -> dict[str, Any] | None:
    rows = read_list(name)
    for idx, row in enumerate(rows):
        if predicate(row):
            updated = {**row, **changes, "updated_at": utc_now()}
            rows[idx] = updated
            write_json(name, rows)
            return updated
    return None


def validate_state() -> list[str]:
    errors: list[str] = []
    expected_lists = [
        "competitions.json",
        "runs.json",
        "submissions.json",
        "profiles.json",
        "experiments.json",
        "notebooks.json",
        "artifacts.json",
        "scout_history.json",
        "tasks.json",
    ]
    for name in expected_lists:
        try:
            value = read_json(name, [])
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: invalid JSON: {exc}")
            continue
        if not isinstance(value, list):
            errors.append(f"{name}: expected list, got {type(value).__name__}")
    prefs = read_json("preferences.json", {})
    if not isinstance(prefs, dict):
        errors.append("preferences.json: expected object")
    for idx, row in enumerate(read_json("profiles.json", [])):
        direction = row.get("metric_direction")
        if direction is not None and direction not in {"maximize", "minimize"}:
            errors.append(f"profiles.json[{idx}].metric_direction: expected one of maximize, minimize")
    for name, fields in REQUIRED_FIELDS.items():
        for idx, row in enumerate(read_json(name, [])):
            for field in fields:
                if row.get(field) in {None, ""}:
                    errors.append(f"{name}[{idx}].{field}: missing required field")
    for idx, row in enumerate(read_json("runs.json", [])):
        failure_class = row.get("failure_class")
        if failure_class is not None and failure_class not in FAILURE_CLASSES:
            errors.append(f"runs.json[{idx}].failure_class: unknown failure class {failure_class}")
    return errors


def ensure_state_files() -> None:
    defaults = {
        "competitions.json": [],
        "runs.json": [],
        "submissions.json": [],
        "profiles.json": [],
        "experiments.json": [],
        "notebooks.json": [],
        "artifacts.json": [],
        "scout_history.json": [],
        "tasks.json": [],
        "preferences.json": {
            "prefer": [
                "tabular",
                "small-to-medium data",
                "clear metric",
                "CPU runnable",
                "active competitions",
                "low barrier to valid submission"
            ],
            "avoid": [
                "requires huge GPUs",
                "unclear rules",
                "external data required",
                "manual labeling",
                "very short deadline"
            ],
            "weekly_scout_day": "Saturday"
        },
    }
    for name, value in defaults.items():
        path = STATE_DIR / name
        if not path.exists():
            write_json(name, value)
    lessons = STATE_DIR / "lessons.md"
    if not lessons.exists():
        lessons.write_text("# Lessons\n\n", encoding="utf-8")
    observability = STATE_DIR / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    metrics = observability / "metrics.json"
    if not metrics.exists():
        metrics.write_text("{}\n", encoding="utf-8")
