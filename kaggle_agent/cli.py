import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .artifacts import find_output_artifact, find_run, record_output_artifact, review_output_artifact
from .config import PROJECT_ROOT, STATE_DIR
from .drive_sync import push_roots
from .kaggle_cli import kernel_output, kernel_status, list_competitions as kaggle_list_competitions
from .scout import build_scout_item
from .state import (
    append_jsonl,
    ensure_state_files,
    read_json,
    read_list,
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
    existing = next(
        (item for item in read_list("experiments.json") if item.get("experiment_key") == row["experiment_key"]),
        None,
    )
    if existing and not args.allow_duplicate:
        raise SystemExit(
            f"duplicate experiment: {existing.get('experiment_id')} already has key {row['experiment_key']}"
        )
    emit(upsert_by_key("experiments.json", "experiment_id", row), args.json)


def list_experiments(args: argparse.Namespace) -> None:
    ensure_state_files()
    rows = read_list("experiments.json")
    if args.competition_slug:
        rows = [row for row in rows if row.get("competition_slug") == args.competition_slug]
    if args.status:
        rows = [row for row in rows if row.get("status") == args.status]
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
    pending_runs = [row for row in runs if str(row.get("status", "")).upper() not in terminal]
    pending_experiments = [
        row for row in experiments if str(row.get("status", "")).lower() not in {"complete", "submitted", "stopped"}
    ]
    context = {
        "summary": {
            "competitions": len(read_json("competitions.json", [])),
            "experiments": len(experiments),
            "pending_experiments": len(pending_experiments),
            "runs": len(runs),
            "pending_runs": len(pending_runs),
            "submissions": len(read_json("submissions.json", [])),
            "scout_snapshots": len(read_json("scout_history.json", [])),
            "notebooks": len(read_json("notebooks.json", [])),
            "artifacts": len(read_json("artifacts.json", [])),
        },
        "state_files": [
            "state/competitions.json",
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
    record = {
        **current,
        "session_id": args.session_id,
        "ended_at": utc_now(),
        "personas_used": args.personas or [],
        "state_writes": args.state_writes or [],
        "outcome": args.outcome,
        "human_interventions": args.human_interventions,
        "tokens": {
            "input": args.tokens_input,
            "output": args.tokens_output,
            "cache_read": args.tokens_cache_read,
            "source": args.token_source,
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
    sessions = read_sessions_jsonl()
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
                "families": {},
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
        score = row.get("public_score")
        if score is not None and (data["best_public_score"] is None or score > data["best_public_score"]):
            data["best_public_score"] = score

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
    exp_list.add_argument("--json", action="store_true")
    exp_list.set_defaults(func=list_experiments)

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
