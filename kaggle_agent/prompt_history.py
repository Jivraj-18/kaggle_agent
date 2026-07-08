import json
import re
from pathlib import Path
from typing import Any

SYNTHETIC_PREFIXES = (
    "<local-command-stdout>",
    "<local-command-stderr>",
    "<local-command-caveat>",
    "<environment_context>",
    "<turn_aborted>",
    "<task-notification>",
    "The following is the Codex agent history",
)


def claude_project_slug(project_root: Path) -> str:
    """Claude Code's ~/.claude/projects/<slug>/ naming: every run of
    non-alphanumeric characters (/, _, ., etc.) becomes a single "-"."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", str(project_root))


def extract_text(content: Any) -> str | None:
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") in ("text", "input_text")]
        text = "\n".join(p for p in parts if p)
    else:
        return None
    text = text.strip()
    if not text or any(text.startswith(p) for p in SYNTHETIC_PREFIXES):
        return None
    return text


def latest_claude_prompt(transcript_path: Path) -> str | None:
    if not transcript_path.exists():
        return None
    latest: str | None = None
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "user" or row.get("isMeta"):
            continue
        text = extract_text((row.get("message") or {}).get("content"))
        if text:
            latest = text
    return latest


def codex_sessions_for_cwd(sessions_dir: Path, cwd: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not sessions_dir.exists():
        return results
    for path in sorted(sessions_dir.rglob("*.jsonl")):
        session_id: str | None = None
        matches_cwd = False
        prompts: list[str] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("type") == "session_meta":
                    payload = row.get("payload") or {}
                    session_id = payload.get("id")
                    matches_cwd = payload.get("cwd") == cwd
                elif row.get("type") == "response_item":
                    payload = row.get("payload") or {}
                    if payload.get("type") == "message" and payload.get("role") == "user":
                        text = extract_text(payload.get("content"))
                        if text:
                            prompts.append(text)
        except (json.JSONDecodeError, OSError):
            continue
        if matches_cwd and session_id:
            results.append({"session_id": session_id, "path": str(path), "prompts": prompts})
    return results


def append_prompt(md_path: Path, harness: str, session_id: str, date: str, prompt: str) -> None:
    resume = f"claude --resume {session_id}" if harness == "claude" else f"codex resume {session_id}"
    header = f"## {date} — {harness} — session {session_id}"
    prompt_line = f"- {prompt}"

    md_path.parent.mkdir(parents=True, exist_ok=True)
    text = md_path.read_text(encoding="utf-8") if md_path.exists() else "# Prompt History\n"

    if header not in text:
        section = f"\n{header}\nResume: `{resume}`\n\n{prompt_line}\n"
        text = text.rstrip("\n") + "\n" + section
    else:
        lines = text.splitlines()
        header_idx = lines.index(header)
        next_header_idx = next(
            (i for i in range(header_idx + 1, len(lines)) if lines[i].startswith("## ")), len(lines)
        )
        section_lines = lines[header_idx:next_header_idx]
        if prompt_line in section_lines:
            return
        insert_at = next_header_idx
        while insert_at > header_idx and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        lines[insert_at:insert_at] = [prompt_line]
        text = "\n".join(lines) + "\n"

    md_path.write_text(text, encoding="utf-8")
