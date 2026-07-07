import argparse
import json
from typing import Any

from .kaggle_cli import kernel_status, list_competitions as kaggle_list_competitions
from .scout import build_scout_item
from .state import (
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
        "kernel_slug": args.kernel_slug,
        "version": args.version,
        "status": args.status,
        "outputs_pulled": args.outputs_pulled,
        "submitted": args.submitted,
        "next_action": args.next_action,
        "notes": args.notes or "",
    }
    emit(upsert_by_key("runs.json", "run_id", row), args.json)


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


def add_submission(args: argparse.Namespace) -> None:
    ensure_state_files()
    row = {
        "submission_ref": args.ref,
        "competition_slug": args.competition_slug,
        "kernel_slug": args.kernel_slug,
        "version": args.version,
        "file_name": args.file_name,
        "status": args.status,
        "public_score": args.public_score,
        "private_score": args.private_score,
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
        "competitions": len(read_json("competitions.json", [])),
        "runs": len(read_json("runs.json", [])),
        "submissions": len(read_json("submissions.json", [])),
        "scout_snapshots": len(read_json("scout_history.json", [])),
        "tasks": len(read_json("tasks.json", [])),
    }
    emit(summary, args.json)


def validate(args: argparse.Namespace) -> None:
    ensure_state_files()
    errors = validate_state()
    if errors:
        emit({"ok": False, "errors": errors}, args.json)
        raise SystemExit(1)
    emit({"ok": True, "errors": []}, args.json)


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

    valid = sub.add_parser("validate-state")
    valid.add_argument("--json", action="store_true")
    valid.set_defaults(func=validate)

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

    runs = sub.add_parser("runs")
    runs_sub = runs.add_subparsers(dest="run_command", required=True)
    run_add = runs_sub.add_parser("add")
    run_add.add_argument("--run-id")
    run_add.add_argument("--competition-slug", required=True)
    run_add.add_argument("--kernel-slug", required=True)
    run_add.add_argument("--version", type=int)
    run_add.add_argument("--status", default="pushed")
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

    submissions = sub.add_parser("submissions")
    submissions_sub = submissions.add_subparsers(dest="submission_command", required=True)
    sub_add = submissions_sub.add_parser("add")
    sub_add.add_argument("--ref", required=True)
    sub_add.add_argument("--competition-slug", required=True)
    sub_add.add_argument("--kernel-slug")
    sub_add.add_argument("--version", type=int)
    sub_add.add_argument("--file-name", default="submission.csv")
    sub_add.add_argument("--status", default="COMPLETE")
    sub_add.add_argument("--public-score", type=float)
    sub_add.add_argument("--private-score", type=float)
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
