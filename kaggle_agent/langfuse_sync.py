from pathlib import Path
from typing import Any

from .prompt_history import (
    claude_project_slug,
    claude_session_turns,
    claude_sessions_for_project,
    codex_session_turns,
    codex_sessions_for_cwd,
)


def pair_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse ordered user/assistant turns (see claude_session_turns,
    codex_session_turns) into one exchange per user prompt: a user turn
    starts an exchange, every assistant turn's text before the next user
    turn is appended to its output. Langfuse's generation concept is
    input+output per call, not one row per message."""
    exchanges: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for turn in turns:
        if turn["role"] == "user":
            if current is not None:
                exchanges.append(current)
            current = {"input": turn["text"], "output": None, "model": None, "timestamp": turn["timestamp"]}
        else:
            if current is None:
                current = {"input": None, "output": turn["text"], "model": turn["model"], "timestamp": turn["timestamp"]}
            else:
                current["output"] = f"{current['output']}\n{turn['text']}" if current["output"] else turn["text"]
                current["model"] = turn["model"] or current["model"]
    if current is not None:
        exchanges.append(current)
    return exchanges


def discover_sessions(
    project_root: Path,
    session_records: list[dict[str, Any]],
    claude_projects_dir: Path,
    codex_sessions_dir: Path,
) -> list[dict[str, Any]]:
    """Every real transcript for this project on disk (source of truth --
    state/observability/sessions.jsonl is known to drift/miss real sessions,
    see docs/architecture.md#observability), enriched with a matching
    sessions.jsonl record's metadata where one exists."""
    by_id = {row["session_id"]: row for row in session_records if row.get("session_id")}
    slug = claude_project_slug(project_root)
    sessions = []
    for row in claude_sessions_for_project(claude_projects_dir, slug):
        sessions.append(
            {
                **by_id.get(row["session_id"], {}),
                "session_id": row["session_id"],
                "harness": "claude",
                "transcript_path": str(claude_projects_dir / slug / f"{row['session_id']}.jsonl"),
            }
        )
    for row in codex_sessions_for_cwd(codex_sessions_dir, str(project_root)):
        sessions.append(
            {
                **by_id.get(row["session_id"], {}),
                "session_id": row["session_id"],
                "harness": "codex",
                "transcript_path": row["path"],
            }
        )
    return sessions


def push_session(client: Any, session: dict[str, Any], exchanges: list[dict[str, Any]]) -> str:
    """Push one session as one Langfuse trace, one generation per exchange,
    grouped via Langfuse Sessions (session_id) for the competition/session
    drill-down view. Requires the `langfuse` package (pip/uv install
    kaggle-agent[observability])."""
    from langfuse import propagate_attributes

    session_id = session["session_id"]
    trace_id = client.create_trace_id(seed=session_id)
    tags = [f"harness:{session.get('harness')}"]
    for key in ("competition_slug", "skill_invoked", "model"):
        if session.get(key):
            tags.append(f"{key}:{session[key]}")
    metadata = {
        key: session[key]
        for key in ("harness", "model", "skill_invoked", "competition_slug", "outcome")
        if session.get(key)
    }
    with propagate_attributes(
        session_id=session_id,
        tags=tags,
        metadata=metadata,
        trace_name=f"{session.get('harness')}:{session.get('skill_invoked') or 'session'}:{session_id}",
    ):
        for i, exchange in enumerate(exchanges):
            observation = client.start_observation(
                trace_context={"trace_id": trace_id},
                name=f"turn-{i + 1}",
                as_type="generation",
                input=exchange["input"],
                output=exchange["output"],
                model=exchange["model"],
            )
            observation.end()
    return trace_id


def sync_all(
    client: Any,
    project_root: Path,
    session_records: list[dict[str, Any]],
    claude_projects_dir: Path,
    codex_sessions_dir: Path,
    already_synced: set[str],
) -> list[str]:
    """Push every not-yet-synced real session for this project. Returns the
    session_ids pushed this run, for the caller to persist as newly synced."""
    synced_now = []
    for session in discover_sessions(project_root, session_records, claude_projects_dir, codex_sessions_dir):
        session_id = session["session_id"]
        if session_id in already_synced:
            continue
        transcript = Path(session["transcript_path"])
        turns_fn = claude_session_turns if session["harness"] == "claude" else codex_session_turns
        exchanges = pair_turns(turns_fn(transcript))
        if not exchanges:
            continue
        push_session(client, session, exchanges)
        synced_now.append(session_id)
    return synced_now
