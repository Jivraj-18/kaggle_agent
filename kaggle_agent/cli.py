import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .artifacts import find_output_artifact, find_run, record_output_artifact, review_output_artifact, sha256_dir
from .config import PROJECT_ROOT, STATE_DIR
from .drive_sync import push_roots
from .kaggle_cli import (
    competition_submissions,
    competition_submit,
    kernel_output,
    kernel_push,
    kernel_status,
    list_competitions as kaggle_list_competitions,
)
from .scout import build_scout_item
from .token_usage import parse_claude_transcript
from .state import (
    append_jsonl,
    ensure_state_files,
    read_json,
    read_list,
    parse_utc,
    update_matching,
    upsert_by_key,
    utc_now,
    validate_state,
    write_json,
)


def emit(value: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    if isinstance(value, list):
        if not value:
            print("No records.")
            return
        for row in value:
            print(json.dumps(row, sort_keys=True))
    else:
        print(json.dumps(value, sort_keys=True))


def add_competition(args: argparse.Namespace) -> None:
    ensure_state_files()
    slug = args.slug.strip()
    row = {
        "slug": slug,
        "title": args.title or slug,
        "url": args.url or f"https://www.kaggle.com/competitions/{slug}",
        "decision": args.decision,
        "notes": args.notes or "",
    }
    emit(upsert_by_key("competitions.json", "slug", row), args.json)


def list_competitions(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("competitions.json")
    if args.decision:
        rows = [row for row in rows if row.get("decision") == args.decision]
    emit(rows, args.json)


def parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean, got {value!r}")


def add_profile(args: argparse.Namespace) -> None:
    ensure_state_files()
    row = {
        "competition_slug": args.competition_slug,
        "problem_type": args.problem_type,
        "metric_name": args.metric_name,
        "metric_direction": args.metric_direction,
        "submission_id_column": args.submission_id_column,
        "submission_target_column": args.submission_target_column,
        "internet_allowed": args.internet_allowed,
        "external_data_allowed": args.external_data_allowed,
        "notes": args.notes or "",
    }
    emit(upsert_by_key("profiles.json", "competition_slug", row), args.json)


def list_profiles(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("profiles.json")
    if args.competition_slug:
        rows = [row for row in rows if row.get("competition_slug") == args.competition_slug]
    emit(rows, args.json)


def add_run(args: argparse.Namespace) -> None:
    ensure_state_files()
    row = {
        "run_id": args.run_id or f"{args.kernel_slug}:v{args.version or 'latest'}",
        "competition_slug": args.competition_slug,
        "experiment_key": args.experiment_key,
        "kernel_slug": args.kernel_slug,
        "version": args.version,
        "status": args.status,
        "failure_class": args.failure_class,
        "outputs_pulled": args.outputs_pulled,
        "submitted": args.submitted,
        "next_action": args.next_action,
        "notes": args.notes or "",
    }
    emit(upsert_by_key("runs.json", "run_id", row), args.json)


def file_sha256(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def experiment_key(row: dict[str, Any]) -> str:
    payload = {
        "competition_slug": row["competition_slug"],
        "hypothesis": " ".join(row["hypothesis"].lower().split()),
        "plan_sha256": row.get("plan_sha256"),
        "notebook_sha256": row.get("notebook_sha256"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def add_experiment(args: argparse.Namespace) -> None:
    ensure_state_files()
    row = {
        "experiment_id": args.experiment_id or f"{args.competition_slug}-{utc_now().replace(':', '').replace('-', '')}",
        "competition_slug": args.competition_slug,
        "phase": args.phase,
        "family": args.family,
        "what_changed": args.what_changed,
        "hypothesis": args.hypothesis,
        "plan_file": str(args.plan_file) if args.plan_file else None,
        "notebook_file": str(args.notebook_file) if args.notebook_file else None,
        "plan_sha256": file_sha256(args.plan_file),
        "notebook_sha256": file_sha256(args.notebook_file),
        "status": args.status,
        "run_id": args.run_id,
        "cv_score": args.cv_score,
        "cv_baseline": args.cv_baseline,
        "lb_score": args.lb_score,
        "outcome": args.outcome,
        "notes": args.notes or "",
    }
    row["experiment_key"] = args.experiment_key or experiment_key(row)
    experiments = read_list("experiments.json")
    existing = next((item for item in experiments if item.get("experiment_key") == row["experiment_key"]), None)
    if existing and not args.allow_duplicate:
        raise SystemExit(
            f"duplicate experiment: {existing.get('experiment_id')} already has key {row['experiment_key']}"
        )
    family_repeat = next(
        (
            item
            for item in experiments
            if item.get("competition_slug") == row["competition_slug"] and item.get("family") == row.get("family")
        ),
        None,
    )
    if family_repeat and row.get("family") and not row.get("what_changed"):
        raise SystemExit(f"what_changed required for another {row['family']} experiment")
    emit(upsert_by_key("experiments.json", "experiment_id", row), args.json)


def list_experiments(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("experiments.json")
    if args.competition_slug:
        rows = [row for row in rows if row.get("competition_slug") == args.competition_slug]
    if args.status:
        rows = [row for row in rows if row.get("status") == args.status]
    if args.family:
        rows = [row for row in rows if row.get("family") == args.family]
    emit(rows, args.json)


def list_runs(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("runs.json")
    if args.status:
        rows = [row for row in rows if row.get("status") == args.status]
    if args.pending:
        terminal = {"COMPLETE", "ERROR", "FAILED", "CANCELED", "CANCELLED"}
        rows = [row for row in rows if str(row.get("status", "")).upper() not in terminal]
    emit(rows, args.json)


def add_notebook(args: argparse.Namespace) -> None:
    ensure_state_files()
    row = {
        "notebook_id": args.notebook_id or f"{args.kernel_slug}:v{args.version or 'latest'}",
        "competition_slug": args.competition_slug,
        "experiment_key": args.experiment_key,
        "kernel_slug": args.kernel_slug,
        "version": args.version,
        "drive_file_id": args.drive_file_id,
        "source_sha256": args.source_sha256,
        "status": args.status,
        "notes": args.notes or "",
    }
    emit(upsert_by_key("notebooks.json", "notebook_id", row), args.json)


def notebook_metadata_errors(metadata: dict[str, Any], competition_slug: str, kernel_slug: str | None = None) -> list[str]:
    profile = next((row for row in read_list("profiles.json") if row.get("competition_slug") == competition_slug), {})
    errors: list[str] = []
    if competition_slug not in (metadata.get("competition_sources") or []):
        errors.append(f"competition_sources: missing {competition_slug}")
    if kernel_slug and metadata.get("id") != kernel_slug:
        errors.append(f"id: expected {kernel_slug}")
    if profile.get("internet_allowed") is False and metadata.get("enable_internet") is True:
        errors.append("enable_internet: profile forbids internet")
    return errors


def push_notebook(args: argparse.Namespace) -> None:
    ensure_state_files()
    if not args.path.is_dir():
        raise SystemExit(f"notebook path is not a directory: {args.path}")
    metadata_file = args.path / "kernel-metadata.json"
    if metadata_file.exists():
        errors = notebook_metadata_errors(
            json.loads(metadata_file.read_text(encoding="utf-8")),
            args.competition_slug,
            args.kernel_slug,
        )
        if errors:
            emit({"ok": False, "errors": errors}, args.json)
            raise SystemExit(1)
    result = kernel_push(str(args.path))
    if result.returncode != 0:
        emit(
            {
                "ok": False,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            args.json,
        )
        raise SystemExit(result.returncode)

    notebook_id = args.notebook_id or f"{args.kernel_slug}:v{args.version or 'latest'}"
    notebook = upsert_by_key(
        "notebooks.json",
        "notebook_id",
        {
            "notebook_id": notebook_id,
            "competition_slug": args.competition_slug,
            "experiment_key": args.experiment_key,
            "kernel_slug": args.kernel_slug,
            "version": args.version,
            "source_sha256": sha256_dir(args.path),
            "status": "pushed",
            "local_path": str(args.path),
            "last_push_stdout": result.stdout.strip(),
            "last_push_stderr": result.stderr.strip(),
        },
    )
    run = upsert_by_key(
        "runs.json",
        "run_id",
        {
            "run_id": f"{args.kernel_slug}:v{args.version or 'latest'}",
            "competition_slug": args.competition_slug,
            "experiment_key": args.experiment_key,
            "kernel_slug": args.kernel_slug,
            "version": args.version,
            "status": "pushed",
            "outputs_pulled": False,
            "submitted": False,
            "next_action": "check_status",
        },
    )
    emit({"notebook": notebook, "run": run, "kaggle_stdout": result.stdout.strip(), "kaggle_stderr": result.stderr.strip()}, args.json)


def list_notebooks(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("notebooks.json")
    if args.competition_slug:
        rows = [row for row in rows if row.get("competition_slug") == args.competition_slug]
    if args.status:
        rows = [row for row in rows if row.get("status") == args.status]
    emit(rows, args.json)


def validate_notebook_metadata(args: argparse.Namespace) -> None:
    ensure_state_files()
    metadata = json.loads(args.metadata_file.read_text(encoding="utf-8"))
    errors = notebook_metadata_errors(metadata, args.competition_slug)
    result = {"ok": not errors, "errors": errors}
    emit(result, args.json)
    if errors:
        raise SystemExit(1)


def add_task(args: argparse.Namespace) -> None:
    ensure_state_files()
    row = {
        "task_id": args.task_id or f"{args.kind}-{utc_now().replace(':', '').replace('-', '')}",
        "competition_slug": args.competition_slug,
        "kind": args.kind,
        "priority": args.priority,
        "status": "open",
        "notes": args.notes or "",
    }
    emit(upsert_by_key("tasks.json", "task_id", row), args.json)


def list_tasks(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("tasks.json")
    if args.status:
        rows = [row for row in rows if row.get("status") == args.status]
    if args.competition_slug:
        rows = [row for row in rows if row.get("competition_slug") == args.competition_slug]
    emit(rows, args.json)


def complete_task(args: argparse.Namespace) -> None:
    ensure_state_files()
    updated = update_matching("tasks.json", lambda row: row.get("task_id") == args.task_id, {"status": "complete"})
    if not updated:
        raise SystemExit(f"task not found: {args.task_id}")
    emit(updated, args.json)


def check_run(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("runs.json")
    target = next((row for row in rows if row.get("run_id") == args.run_id), None)
    if not target:
        raise SystemExit(f"run not found: {args.run_id}")
    status, result = kernel_status(target["kernel_slug"])
    normalized = status.replace("KernelWorkerStatus.", "")
    changes = {
        "status": normalized,
        "last_checked_at": utc_now(),
        "last_status_stdout": result.stdout.strip(),
        "last_status_stderr": result.stderr.strip(),
    }
    updated = update_matching("runs.json", lambda row: row.get("run_id") == args.run_id, changes)
    if result.returncode != 0:
        emit(updated or changes, args.json)
        raise SystemExit(result.returncode)
    emit(updated or changes, args.json)


def pull_run_output(args: argparse.Namespace) -> None:
    ensure_state_files()
    run = find_run(args.run_id)
    if not run:
        raise SystemExit(f"run not found: {args.run_id}")
    output_dir = args.output_dir or (PROJECT_ROOT / "artifacts" / run["competition_slug"] / run["run_id"].replace("/", "__").replace(":", "__"))
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.from_dir:
        if output_dir.resolve() != args.from_dir.resolve():
            if output_dir.exists():
                shutil.rmtree(output_dir)
            shutil.copytree(args.from_dir, output_dir)
        artifact = record_output_artifact(run, output_dir, "from_dir")
        emit(artifact, args.json)
        return

    result = kernel_output(run["kernel_slug"], str(output_dir))
    if result.returncode != 0:
        emit(
            {
                "ok": False,
                "run_id": args.run_id,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            args.json,
        )
        raise SystemExit(result.returncode)
    artifact = record_output_artifact(run, output_dir, "kaggle_cli")
    artifact["last_output_stdout"] = result.stdout.strip()
    artifact["last_output_stderr"] = result.stderr.strip()
    emit(artifact, args.json)


def review_run_output(args: argparse.Namespace) -> None:
    ensure_state_files()
    run = find_run(args.run_id)
    if not run:
        raise SystemExit(f"run not found: {args.run_id}")
    artifact = find_output_artifact(args.run_id)
    if not artifact:
        raise SystemExit(f"output artifact not found for run: {args.run_id}")
    emit(review_output_artifact(run, artifact, args.sample_submission), args.json)


def add_submission(args: argparse.Namespace) -> None:
    ensure_state_files()
    row = {
        "submission_ref": args.ref,
        "competition_slug": args.competition_slug,
        "experiment_key": args.experiment_key,
        "kernel_slug": args.kernel_slug,
        "version": args.version,
        "file_name": args.file_name,
        "status": args.status,
        "cv_score": args.cv_score,
        "public_score": args.public_score,
        "private_score": args.private_score,
        "rank": args.rank,
        "percentile": args.percentile,
        "valid": args.valid,
        "notes": args.notes or "",
    }
    emit(upsert_by_key("submissions.json", "submission_ref", row), args.json)


def submit_file(args: argparse.Namespace) -> None:
    ensure_state_files()
    if not args.file.is_file():
        raise SystemExit(f"submission file not found: {args.file}")
    result = competition_submit(args.competition_slug, str(args.file), args.message)
    if result.returncode != 0:
        emit(
            {
                "ok": False,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            args.json,
        )
        raise SystemExit(result.returncode)

    digest = file_sha256(args.file)
    row = {
        "submission_ref": args.ref or f"{args.competition_slug}:{digest[:12]}",
        "competition_slug": args.competition_slug,
        "experiment_key": args.experiment_key,
        "kernel_slug": args.kernel_slug,
        "version": args.version,
        "file_name": args.file.name,
        "file_path": str(args.file),
        "file_sha256": digest,
        "message": args.message,
        "status": "submitted",
        "valid": True,
        "submitted_at": utc_now(),
        "last_submit_stdout": result.stdout.strip(),
        "last_submit_stderr": result.stderr.strip(),
    }
    submission = upsert_by_key("submissions.json", "submission_ref", row)
    if args.kernel_slug:
        run_id = f"{args.kernel_slug}:v{args.version or 'latest'}"
        update_matching(
            "runs.json",
            lambda item: item.get("run_id") == run_id,
            {"submitted": True, "next_action": "check_leaderboard"},
        )
    emit({"submission": submission, "kaggle_stdout": result.stdout.strip(), "kaggle_stderr": result.stderr.strip()}, args.json)


def maybe_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def refresh_submissions(args: argparse.Namespace) -> None:
    ensure_state_files()
    result = competition_submissions(args.competition_slug)
    if result.returncode != 0:
        emit(
            {
                "ok": False,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            args.json,
        )
        raise SystemExit(result.returncode)

    raw_rows = json.loads(result.stdout or "[]")
    existing = {row.get("submission_ref"): row for row in read_list("submissions.json")}
    refreshed = []
    for idx, raw in enumerate(raw_rows):
        ref = str(raw.get("ref") or raw.get("id") or raw.get("submissionId") or f"{args.competition_slug}:{idx}")
        previous = existing.get(ref, {})
        row = {
            "submission_ref": ref,
            "competition_slug": args.competition_slug,
            "experiment_key": previous.get("experiment_key"),
            "kernel_slug": previous.get("kernel_slug"),
            "version": previous.get("version"),
            "file_name": raw.get("fileName") or previous.get("file_name"),
            "status": raw.get("status") or previous.get("status"),
            "public_score": maybe_float(raw.get("publicScore")),
            "private_score": maybe_float(raw.get("privateScore")),
            "valid": str(raw.get("status", "")).lower() in {"complete", "completed", "submitted"},
            "raw": raw,
        }
        refreshed.append(upsert_by_key("submissions.json", "submission_ref", row))
    emit(refreshed, args.json)


def list_submissions(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("submissions.json")
    if args.competition_slug:
        rows = [row for row in rows if row.get("competition_slug") == args.competition_slug]
    emit(rows, args.json)


def state_summary(args: argparse.Namespace) -> None:
    ensure_state_files()
    summary = {
        "artifacts": len(read_json("artifacts.json", [])),
        "competitions": len(read_json("competitions.json", [])),
        "experiments": len(read_json("experiments.json", [])),
        "notebooks": len(read_json("notebooks.json", [])),
        "runs": len(read_json("runs.json", [])),
        "submissions": len(read_json("submissions.json", [])),
        "scout_snapshots": len(read_json("scout_history.json", [])),
        "tasks": len(read_json("tasks.json", [])),
    }
    emit(summary, args.json)


def resume_context(args: argparse.Namespace) -> None:
    ensure_state_files()
    terminal = {"COMPLETE", "ERROR", "FAILED", "CANCELED", "CANCELLED"}
    runs = read_list("runs.json")
    experiments = read_list("experiments.json")
    tasks = read_list("tasks.json")
    pending_runs = [row for row in runs if str(row.get("status", "")).upper() not in terminal]
    pending_experiments = [
        row for row in experiments if str(row.get("status", "")).lower() not in {"complete", "submitted", "stopped"}
    ]
    open_tasks = [row for row in tasks if row.get("status") == "open"]

    competition_status: dict[str, dict[str, Any]] = {}

    def status_for(slug: str | None) -> dict[str, Any] | None:
        if not slug:
            return None
        return competition_status.setdefault(
            slug,
            {"pending_runs": 0, "pending_experiments": 0, "open_tasks": 0, "next_actions": []},
        )

    def add_action(status: dict[str, Any] | None, action: str | None) -> None:
        if status is not None and action and action not in status["next_actions"]:
            status["next_actions"].append(action)

    for row in pending_runs:
        status = status_for(row.get("competition_slug"))
        if status is not None:
            status["pending_runs"] += 1
            add_action(status, row.get("next_action"))
    for row in pending_experiments:
        status = status_for(row.get("competition_slug"))
        if status is not None:
            status["pending_experiments"] += 1
            add_action(status, "plan_or_push")
    for row in open_tasks:
        status = status_for(row.get("competition_slug"))
        if status is not None:
            status["open_tasks"] += 1
            add_action(status, row.get("kind"))

    context = {
        "summary": {
            "competitions": len(read_json("competitions.json", [])),
            "profiles": len(read_json("profiles.json", [])),
            "experiments": len(experiments),
            "pending_experiments": len(pending_experiments),
            "runs": len(runs),
            "pending_runs": len(pending_runs),
            "submissions": len(read_json("submissions.json", [])),
            "scout_snapshots": len(read_json("scout_history.json", [])),
            "notebooks": len(read_json("notebooks.json", [])),
            "artifacts": len(read_json("artifacts.json", [])),
            "open_tasks": len(open_tasks),
        },
        "state_files": [
            "state/competitions.json",
            "state/profiles.json",
            "state/experiments.json",
            "state/runs.json",
            "state/submissions.json",
            "state/scout_history.json",
            "state/notebooks.json",
            "state/artifacts.json",
            "state/lessons.md",
            "state/observability/sessions.jsonl",
            "state/observability/metrics.json",
        ],
        "pending_runs": pending_runs,
        "pending_experiments": pending_experiments,
        "open_tasks": open_tasks,
        "competition_status": competition_status,
        "agent_instruction": (
            "Use this as resume context only. For Kaggle updates, check pending_runs once and pull outputs only "
            "for terminal runs. For new competitions, run scout-competitions and review raw rows with lessons."
        ),
    }
    emit(context, args.json)


def start_session(args: argparse.Namespace) -> None:
    ensure_state_files()
    now = utc_now()
    safe_time = now.replace(":", "").replace("-", "")
    session_id = args.session_id or f"{safe_time}-{args.harness}"
    record = {
        "session_id": session_id,
        "harness": args.harness,
        "model": args.model,
        "skill_invoked": args.skill,
        "competition_slug": args.competition_slug,
        "started_at": now,
    }
    write_json("observability/current_session.json", record)
    emit(record, args.json)


def end_session(args: argparse.Namespace) -> None:
    ensure_state_files()
    current = read_json("observability/current_session.json", {})
    if current and current.get("session_id") != args.session_id:
        raise SystemExit(f"active session mismatch: {current.get('session_id')} != {args.session_id}")
    tokens_input = args.tokens_input
    tokens_output = args.tokens_output
    tokens_cache_read = args.tokens_cache_read
    token_source = args.token_source
    model = current.get("model")
    if args.transcript_file:
        transcript_path = Path(args.transcript_file)
        if not transcript_path.exists():
            raise SystemExit(f"transcript file not found: {transcript_path}")
        usage = parse_claude_transcript(transcript_path)
        tokens_input = usage["input"]
        tokens_output = usage["output"]
        tokens_cache_read = usage["cache_read"]
        token_source = "claude-transcript-parse"
        model = usage["model"] or model
    record = {
        **current,
        "session_id": args.session_id,
        "model": model,
        "ended_at": utc_now(),
        "personas_used": args.personas or [],
        "state_writes": args.state_writes or [],
        "outcome": args.outcome,
        "human_interventions": args.human_interventions,
        "tokens": {
            "input": tokens_input,
            "output": tokens_output,
            "cache_read": tokens_cache_read,
            "source": token_source,
        },
        "estimated_cost_usd": args.estimated_cost_usd,
    }
    append_jsonl("observability/sessions.jsonl", record)
    emit(record, args.json)


def list_sessions(args: argparse.Namespace) -> None:
    ensure_state_files()
    path = STATE_DIR / "observability" / "sessions.jsonl"
    rows: list[dict[str, Any]] = []
    if path.exists():
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    emit(rows, args.json)


def read_sessions_jsonl() -> list[dict[str, Any]]:
    path = STATE_DIR / "observability" / "sessions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def recompute_metrics(args: argparse.Namespace) -> None:
    ensure_state_files()
    experiments = read_list("experiments.json")
    runs = read_list("runs.json")
    submissions = read_list("submissions.json")
    profiles = read_list("profiles.json")
    competition_records = read_list("competitions.json")
    sessions = read_sessions_jsonl()
    metric_directions = {row.get("competition_slug"): row.get("metric_direction") for row in profiles}
    joined_at = {row.get("slug"): parse_utc(row.get("created_at")) for row in competition_records}
    first_valid_submission_at: dict[str, datetime] = {}
    competitions: dict[str, dict[str, Any]] = {}

    def bucket(slug: str | None) -> dict[str, Any]:
        key = slug or "unknown"
        return competitions.setdefault(
            key,
            {
                "experiments": 0,
                "runs": 0,
                "failed_runs": 0,
                "submissions": 0,
                "valid_submissions": 0,
                "best_public_score": None,
                "score_history": [],
                "metric_direction": metric_directions.get(key),
                "families": {},
                "sessions": 0,
                "tokens": {"input": 0, "output": 0, "cache_read": 0},
                "estimated_cost_usd": 0,
                "failed_run_rate": None,
                "cost_per_valid_submission": None,
                "days_to_first_valid_submission": None,
            },
        )

    for row in experiments:
        data = bucket(row.get("competition_slug"))
        data["experiments"] += 1
        family = row.get("family") or "unknown"
        data["families"][family] = data["families"].get(family, 0) + 1

    for row in runs:
        data = bucket(row.get("competition_slug"))
        data["runs"] += 1
        if str(row.get("status", "")).upper() in {"ERROR", "FAILED", "CANCELED", "CANCELLED"}:
            data["failed_runs"] += 1

    for row in submissions:
        data = bucket(row.get("competition_slug"))
        data["submissions"] += 1
        if row.get("valid"):
            data["valid_submissions"] += 1
            slug = row.get("competition_slug")
            submitted_at = parse_utc(row.get("submitted_at") or row.get("created_at"))
            if slug and submitted_at is not None:
                current = first_valid_submission_at.get(slug)
                if current is None or submitted_at < current:
                    first_valid_submission_at[slug] = submitted_at
        score = row.get("public_score")
        if score is not None:
            data["score_history"].append(
                {
                    "submission_ref": row.get("submission_ref"),
                    "experiment_key": row.get("experiment_key"),
                    "public_score": score,
                    "private_score": row.get("private_score"),
                    "cv_score": row.get("cv_score"),
                    "rank": row.get("rank"),
                    "percentile": row.get("percentile"),
                    "valid": row.get("valid"),
                    "submitted_at": row.get("submitted_at") or row.get("created_at"),
                }
            )
        if score is not None and (
            data["best_public_score"] is None
            or (data.get("metric_direction") == "minimize" and score < data["best_public_score"])
            or (data.get("metric_direction") != "minimize" and score > data["best_public_score"])
        ):
            data["best_public_score"] = score

    for row in sessions:
        if not row.get("competition_slug"):
            continue
        data = bucket(row.get("competition_slug"))
        tokens = row.get("tokens") or {}
        data["sessions"] += 1
        data["tokens"]["input"] += tokens.get("input") or 0
        data["tokens"]["output"] += tokens.get("output") or 0
        data["tokens"]["cache_read"] += tokens.get("cache_read") or 0
        data["estimated_cost_usd"] += row.get("estimated_cost_usd") or 0

    for slug, data in competitions.items():
        data["score_history"].sort(key=lambda row: row.get("submitted_at") or "")
        if data["runs"] > 0:
            data["failed_run_rate"] = data["failed_runs"] / data["runs"]
        if data["valid_submissions"] > 0:
            data["cost_per_valid_submission"] = data["estimated_cost_usd"] / data["valid_submissions"]
        join_time = joined_at.get(slug)
        first_valid_time = first_valid_submission_at.get(slug)
        if join_time is not None and first_valid_time is not None:
            data["days_to_first_valid_submission"] = (first_valid_time - join_time).total_seconds() / 86400

    metrics = {
        "generated_at": utc_now(),
        "competitions": competitions,
        "sessions": {
            "count": len(sessions),
            "total_input_tokens": sum((row.get("tokens") or {}).get("input") or 0 for row in sessions),
            "total_output_tokens": sum((row.get("tokens") or {}).get("output") or 0 for row in sessions),
            "total_cache_read_tokens": sum((row.get("tokens") or {}).get("cache_read") or 0 for row in sessions),
            "estimated_cost_usd": sum(row.get("estimated_cost_usd") or 0 for row in sessions),
        },
    }
    write_json("observability/metrics.json", metrics)
    emit(metrics, args.json)


def validate(args: argparse.Namespace) -> None:
    ensure_state_files()
    errors = validate_state()
    if errors:
        emit({"ok": False, "errors": errors}, args.json)
        raise SystemExit(1)
    emit({"ok": True, "errors": []}, args.json)


def drive_sync_push(args: argparse.Namespace) -> None:
    ensure_state_files()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    folder_id = args.folder_id or config["archive_folder_id"]
    roots = args.root or config.get("roots", ["state"])
    emit(push_roots(roots, folder_id), args.json)


def scout_competitions(args: argparse.Namespace) -> None:
    ensure_state_files()
    items: list[dict[str, Any]] = []
    source_errors: list[dict[str, Any]] = []
    if args.from_file:
        raw = json.loads(args.from_file.read())
        group = args.groups[0] if args.groups else "file"
        items.extend(build_scout_item(row, group, idx) for idx, row in enumerate(raw))
    else:
        for group in args.groups:
            rows, result = kaggle_list_competitions(group=group, page_size=args.page_size, search=args.search)
            if result.returncode != 0:
                source_errors.append(
                    {
                        "group": group,
                        "returncode": result.returncode,
                        "stderr": result.stderr.strip(),
                        "stdout": result.stdout.strip(),
                    }
                )
                continue
            items.extend(build_scout_item(row, group, idx) for idx, row in enumerate(rows))

    selected = items[: args.limit]
    snapshot = {
        "scouted_at": utc_now(),
        "groups": args.groups,
        "search": args.search,
        "limit": args.limit,
        "source_errors": source_errors,
        "agent_instruction": "Review items[].raw directly. Deterministic code has not scored or summarized these competitions.",
        "items": selected,
    }
    history = read_list("scout_history.json")
    history.append(snapshot)
    write_json("scout_history.json", history)

    if args.json:
        emit(snapshot, True)
        return
    if source_errors:
        print(f"Source errors: {len(source_errors)}")
    emit(selected, False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kaggle-agent")
    parser.set_defaults(func=None)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-state")
    init.set_defaults(func=lambda args: (ensure_state_files(), print("initialized state files")))

    summary = sub.add_parser("state-summary")
    summary.add_argument("--json", action="store_true")
    summary.set_defaults(func=state_summary)

    resume = sub.add_parser("resume-context")
    resume.add_argument("--json", action="store_true")
    resume.set_defaults(func=resume_context)

    sessions = sub.add_parser("sessions")
    sessions_sub = sessions.add_subparsers(dest="session_command", required=True)
    sess_start = sessions_sub.add_parser("start")
    sess_start.add_argument("--session-id")
    sess_start.add_argument("--harness", required=True)
    sess_start.add_argument("--model")
    sess_start.add_argument("--skill")
    sess_start.add_argument("--competition-slug")
    sess_start.add_argument("--json", action="store_true")
    sess_start.set_defaults(func=start_session)
    sess_end = sessions_sub.add_parser("end")
    sess_end.add_argument("session_id")
    sess_end.add_argument("--outcome", required=True)
    sess_end.add_argument("--personas", nargs="+")
    sess_end.add_argument("--state-writes", nargs="+")
    sess_end.add_argument("--tokens-input", type=int)
    sess_end.add_argument("--tokens-output", type=int)
    sess_end.add_argument("--tokens-cache-read", type=int)
    sess_end.add_argument("--token-source")
    sess_end.add_argument(
        "--transcript-file",
        help="Path to a Claude Code transcript JSONL; overrides --tokens-* with parsed totals.",
    )
    sess_end.add_argument("--estimated-cost-usd", type=float)
    sess_end.add_argument("--human-interventions", type=int, default=0)
    sess_end.add_argument("--json", action="store_true")
    sess_end.set_defaults(func=end_session)
    sess_list = sessions_sub.add_parser("list")
    sess_list.add_argument("--json", action="store_true")
    sess_list.set_defaults(func=list_sessions)

    metrics = sub.add_parser("metrics")
    metrics_sub = metrics.add_subparsers(dest="metrics_command", required=True)
    metrics_recompute = metrics_sub.add_parser("recompute")
    metrics_recompute.add_argument("--json", action="store_true")
    metrics_recompute.set_defaults(func=recompute_metrics)

    valid = sub.add_parser("validate-state")
    valid.add_argument("--json", action="store_true")
    valid.set_defaults(func=validate)

    drive_sync = sub.add_parser("drive-sync")
    drive_sync_sub = drive_sync.add_subparsers(dest="drive_sync_command", required=True)
    drive_push = drive_sync_sub.add_parser("push")
    drive_push.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "drive.json")
    drive_push.add_argument("--folder-id")
    drive_push.add_argument("--root", action="append")
    drive_push.add_argument("--json", action="store_true")
    drive_push.set_defaults(func=drive_sync_push)

    scout = sub.add_parser("scout-competitions")
    scout.add_argument(
        "--groups",
        nargs="+",
        default=["general", "community"],
        help="Kaggle competition groups to fetch.",
    )
    scout.add_argument("--search")
    scout.add_argument("--page-size", type=int, default=100)
    scout.add_argument("--limit", type=int, default=20)
    scout.add_argument("--from-file", type=argparse.FileType("r"))
    scout.add_argument("--json", action="store_true")
    scout.set_defaults(func=scout_competitions)

    competitions = sub.add_parser("competitions")
    competitions_sub = competitions.add_subparsers(dest="competition_command", required=True)
    comp_add = competitions_sub.add_parser("add")
    comp_add.add_argument("slug")
    comp_add.add_argument("--title")
    comp_add.add_argument("--url")
    comp_add.add_argument("--decision", default="watch")
    comp_add.add_argument("--notes")
    comp_add.add_argument("--json", action="store_true")
    comp_add.set_defaults(func=add_competition)
    comp_list = competitions_sub.add_parser("list")
    comp_list.add_argument("--decision")
    comp_list.add_argument("--json", action="store_true")
    comp_list.set_defaults(func=list_competitions)

    profiles = sub.add_parser("profiles")
    profiles_sub = profiles.add_subparsers(dest="profile_command", required=True)
    profile_add = profiles_sub.add_parser("add")
    profile_add.add_argument("competition_slug")
    profile_add.add_argument("--problem-type")
    profile_add.add_argument("--metric-name")
    profile_add.add_argument("--metric-direction", choices=["minimize", "maximize"])
    profile_add.add_argument("--submission-id-column")
    profile_add.add_argument("--submission-target-column")
    profile_add.add_argument("--internet-allowed", type=parse_bool)
    profile_add.add_argument("--external-data-allowed", type=parse_bool)
    profile_add.add_argument("--notes")
    profile_add.add_argument("--json", action="store_true")
    profile_add.set_defaults(func=add_profile)
    profile_list = profiles_sub.add_parser("list")
    profile_list.add_argument("--competition-slug")
    profile_list.add_argument("--json", action="store_true")
    profile_list.set_defaults(func=list_profiles)

    experiments = sub.add_parser("experiments")
    experiments_sub = experiments.add_subparsers(dest="experiment_command", required=True)
    exp_add = experiments_sub.add_parser("add")
    exp_add.add_argument("--experiment-id")
    exp_add.add_argument("--competition-slug", required=True)
    exp_add.add_argument("--phase", default="model_building_validation_prediction")
    exp_add.add_argument("--family")
    exp_add.add_argument("--what-changed")
    exp_add.add_argument("--hypothesis", required=True)
    exp_add.add_argument("--plan-file", type=Path)
    exp_add.add_argument("--notebook-file", type=Path)
    exp_add.add_argument("--experiment-key")
    exp_add.add_argument("--status", default="planned")
    exp_add.add_argument("--run-id")
    exp_add.add_argument("--cv-score", type=float)
    exp_add.add_argument("--cv-baseline", type=float)
    exp_add.add_argument("--lb-score", type=float)
    exp_add.add_argument("--outcome")
    exp_add.add_argument("--notes")
    exp_add.add_argument("--allow-duplicate", action="store_true")
    exp_add.add_argument("--json", action="store_true")
    exp_add.set_defaults(func=add_experiment)
    exp_list = experiments_sub.add_parser("list")
    exp_list.add_argument("--competition-slug")
    exp_list.add_argument("--status")
    exp_list.add_argument("--family")
    exp_list.add_argument("--json", action="store_true")
    exp_list.set_defaults(func=list_experiments)

    notebooks = sub.add_parser("notebooks")
    notebooks_sub = notebooks.add_subparsers(dest="notebook_command", required=True)
    notebook_add = notebooks_sub.add_parser("add")
    notebook_add.add_argument("--notebook-id")
    notebook_add.add_argument("--competition-slug", required=True)
    notebook_add.add_argument("--experiment-key")
    notebook_add.add_argument("--kernel-slug", required=True)
    notebook_add.add_argument("--version", type=int)
    notebook_add.add_argument("--drive-file-id")
    notebook_add.add_argument("--source-sha256")
    notebook_add.add_argument("--status", default="created")
    notebook_add.add_argument("--notes")
    notebook_add.add_argument("--json", action="store_true")
    notebook_add.set_defaults(func=add_notebook)
    notebook_list = notebooks_sub.add_parser("list")
    notebook_list.add_argument("--competition-slug")
    notebook_list.add_argument("--status")
    notebook_list.add_argument("--json", action="store_true")
    notebook_list.set_defaults(func=list_notebooks)
    notebook_push = notebooks_sub.add_parser("push")
    notebook_push.add_argument("--path", type=Path, required=True)
    notebook_push.add_argument("--notebook-id")
    notebook_push.add_argument("--competition-slug", required=True)
    notebook_push.add_argument("--experiment-key")
    notebook_push.add_argument("--kernel-slug", required=True)
    notebook_push.add_argument("--version", type=int)
    notebook_push.add_argument("--json", action="store_true")
    notebook_push.set_defaults(func=push_notebook)
    notebook_validate = notebooks_sub.add_parser("validate-metadata")
    notebook_validate.add_argument("metadata_file", type=Path)
    notebook_validate.add_argument("--competition-slug", required=True)
    notebook_validate.add_argument("--json", action="store_true")
    notebook_validate.set_defaults(func=validate_notebook_metadata)

    tasks = sub.add_parser("tasks")
    tasks_sub = tasks.add_subparsers(dest="task_command", required=True)
    task_add = tasks_sub.add_parser("add")
    task_add.add_argument("--task-id")
    task_add.add_argument("--competition-slug")
    task_add.add_argument("--kind", required=True)
    task_add.add_argument("--priority", default="normal")
    task_add.add_argument("--notes")
    task_add.add_argument("--json", action="store_true")
    task_add.set_defaults(func=add_task)
    task_list = tasks_sub.add_parser("list")
    task_list.add_argument("--competition-slug")
    task_list.add_argument("--status")
    task_list.add_argument("--json", action="store_true")
    task_list.set_defaults(func=list_tasks)
    task_complete = tasks_sub.add_parser("complete")
    task_complete.add_argument("task_id")
    task_complete.add_argument("--json", action="store_true")
    task_complete.set_defaults(func=complete_task)

    runs = sub.add_parser("runs")
    runs_sub = runs.add_subparsers(dest="run_command", required=True)
    run_add = runs_sub.add_parser("add")
    run_add.add_argument("--run-id")
    run_add.add_argument("--competition-slug", required=True)
    run_add.add_argument("--experiment-key")
    run_add.add_argument("--kernel-slug", required=True)
    run_add.add_argument("--version", type=int)
    run_add.add_argument("--status", default="pushed")
    run_add.add_argument("--failure-class")
    run_add.add_argument("--outputs-pulled", action="store_true")
    run_add.add_argument("--submitted", action="store_true")
    run_add.add_argument("--next-action", default="check_status")
    run_add.add_argument("--notes")
    run_add.add_argument("--json", action="store_true")
    run_add.set_defaults(func=add_run)
    run_list = runs_sub.add_parser("list")
    run_list.add_argument("--status")
    run_list.add_argument("--pending", action="store_true")
    run_list.add_argument("--json", action="store_true")
    run_list.set_defaults(func=list_runs)
    run_check = runs_sub.add_parser("check")
    run_check.add_argument("run_id")
    run_check.add_argument("--json", action="store_true")
    run_check.set_defaults(func=check_run)
    run_pull = runs_sub.add_parser("pull-output")
    run_pull.add_argument("run_id")
    run_pull.add_argument("--from-dir", type=Path)
    run_pull.add_argument("--output-dir", type=Path)
    run_pull.add_argument("--json", action="store_true")
    run_pull.set_defaults(func=pull_run_output)
    run_review = runs_sub.add_parser("review-output")
    run_review.add_argument("run_id")
    run_review.add_argument("--sample-submission", type=Path)
    run_review.add_argument("--json", action="store_true")
    run_review.set_defaults(func=review_run_output)

    submissions = sub.add_parser("submissions")
    submissions_sub = submissions.add_subparsers(dest="submission_command", required=True)
    sub_add = submissions_sub.add_parser("add")
    sub_add.add_argument("--ref", required=True)
    sub_add.add_argument("--competition-slug", required=True)
    sub_add.add_argument("--experiment-key")
    sub_add.add_argument("--kernel-slug")
    sub_add.add_argument("--version", type=int)
    sub_add.add_argument("--file-name", default="submission.csv")
    sub_add.add_argument("--status", default="COMPLETE")
    sub_add.add_argument("--cv-score", type=float)
    sub_add.add_argument("--public-score", type=float)
    sub_add.add_argument("--private-score", type=float)
    sub_add.add_argument("--rank", type=int)
    sub_add.add_argument("--percentile", type=float)
    sub_add.add_argument("--valid", action="store_true")
    sub_add.add_argument("--notes")
    sub_add.add_argument("--json", action="store_true")
    sub_add.set_defaults(func=add_submission)
    sub_list = submissions_sub.add_parser("list")
    sub_list.add_argument("--competition-slug")
    sub_list.add_argument("--json", action="store_true")
    sub_list.set_defaults(func=list_submissions)
    sub_submit = submissions_sub.add_parser("submit-file")
    sub_submit.add_argument("--competition-slug", required=True)
    sub_submit.add_argument("--file", type=Path, required=True)
    sub_submit.add_argument("--message", required=True)
    sub_submit.add_argument("--ref")
    sub_submit.add_argument("--experiment-key")
    sub_submit.add_argument("--kernel-slug")
    sub_submit.add_argument("--version", type=int)
    sub_submit.add_argument("--json", action="store_true")
    sub_submit.set_defaults(func=submit_file)
    sub_refresh = submissions_sub.add_parser("refresh")
    sub_refresh.add_argument("--competition-slug", required=True)
    sub_refresh.add_argument("--json", action="store_true")
    sub_refresh.set_defaults(func=refresh_submissions)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
        raise SystemExit(2)
    args.func(args)


if __name__ == "__main__":
    main()
