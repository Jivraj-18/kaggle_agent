import csv
import hashlib
import re
from pathlib import Path
from typing import Any

SUBMISSION_FILENAME_RE = re.compile(r"^submission(_[A-Za-z0-9]+)?\.csv$")

from .state import read_list, update_matching, upsert_by_key, utc_now, write_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_dir(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def list_files(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        files.append(
            {
                "name": str(path.relative_to(root)),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return files


def record_output_artifact(run: dict[str, Any], output_dir: Path, source: str) -> dict[str, Any]:
    now = utc_now()
    artifact_id = f"{run['run_id']}-output-{now.replace(':', '').replace('-', '')}"
    artifact = {
        "artifact_id": artifact_id,
        "run_id": run["run_id"],
        "competition_slug": run.get("competition_slug"),
        "experiment_key": run.get("experiment_key"),
        "kind": "kaggle_output",
        "source": source,
        "local_path": str(output_dir),
        "files": list_files(output_dir),
        "created_at": now,
    }
    upsert_by_key("artifacts.json", "artifact_id", artifact)
    update_matching(
        "runs.json",
        lambda row: row.get("run_id") == run["run_id"],
        {
            "outputs_pulled": True,
            "output_artifact_id": artifact_id,
            "output_path": str(output_dir),
            "next_action": "review_outputs",
        },
    )
    return artifact


def find_run(run_id: str) -> dict[str, Any] | None:
    return next((row for row in read_list("runs.json") if row.get("run_id") == run_id), None)


def find_output_artifact(run_id: str) -> dict[str, Any] | None:
    matches = [
        row
        for row in read_list("artifacts.json")
        if row.get("run_id") == run_id and row.get("kind") == "kaggle_output"
    ]
    return matches[-1] if matches else None


def csv_shape(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    return {
        "columns": rows[0] if rows else [],
        "row_count": max(len(rows) - 1, 0),
    }


def review_output_artifact(run: dict[str, Any], artifact: dict[str, Any], sample_submission: Path | None = None) -> dict[str, Any]:
    files = artifact.get("files") or []
    by_name = {row.get("name"): row for row in files}
    passed_checks: list[str] = []
    failed_checks: list[str] = []

    submission_matches = sorted(name for name in by_name if name and SUBMISSION_FILENAME_RE.match(name))
    submission = None
    submission_path = None
    if len(submission_matches) == 1:
        submission_name = submission_matches[0]
        submission = by_name[submission_name]
        submission_path = Path(artifact["local_path"]) / submission_name
        passed_checks.append("submission_csv_present")
        if submission.get("size", 0) > 0:
            passed_checks.append("submission_csv_nonempty")
        else:
            failed_checks.append("submission_csv_nonempty")
    elif len(submission_matches) > 1:
        # A batch variant's output dir should contain exactly one submission_<variant>.csv;
        # more than one means variants overwrote a shared dir instead of using unique filenames.
        failed_checks.append("submission_csv_ambiguous")
    else:
        failed_checks.append("submission_csv_present")

    if submission and sample_submission:
        actual = csv_shape(submission_path)
        expected = csv_shape(sample_submission)
        if actual["columns"] == expected["columns"]:
            passed_checks.append("submission_columns_match_sample")
        else:
            failed_checks.append("submission_columns_match_sample")
        if actual["row_count"] == expected["row_count"]:
            passed_checks.append("submission_row_count_match_sample")
        else:
            failed_checks.append("submission_row_count_match_sample")

    verdict = "submission_candidate" if not failed_checks else "invalid_output"
    next_action = "human_review_submission" if verdict == "submission_candidate" else "triage_output"
    review = {
        "run_id": run["run_id"],
        "artifact_id": artifact["artifact_id"],
        "competition_slug": run.get("competition_slug"),
        "experiment_key": run.get("experiment_key"),
        "verdict": verdict,
        "next_action": next_action,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "reviewed_at": utc_now(),
    }

    rows = read_list("artifacts.json")
    for idx, row in enumerate(rows):
        if row.get("artifact_id") == artifact["artifact_id"]:
            rows[idx] = {**row, "review": review}
            break
    write_json("artifacts.json", rows)
    update_matching("runs.json", lambda row: row.get("run_id") == run["run_id"], {"next_action": next_action})
    upsert_by_key(
        "tasks.json",
        "task_id",
        {
            "task_id": f"{run['run_id']}-{next_action}",
            "competition_slug": run.get("competition_slug"),
            "kind": next_action,
            "priority": "high" if next_action == "human_review_submission" else "normal",
            "status": "open",
            "notes": f"Review output artifact {artifact['artifact_id']}",
        },
    )
    return review
