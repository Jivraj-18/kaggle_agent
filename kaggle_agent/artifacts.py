from pathlib import Path
from typing import Any

from .state import read_list, update_matching, upsert_by_key, utc_now, write_json


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
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


def review_output_artifact(run: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    files = artifact.get("files") or []
    by_name = {row.get("name"): row for row in files}
    passed_checks: list[str] = []
    failed_checks: list[str] = []

    submission = by_name.get("submission.csv")
    if submission:
        passed_checks.append("submission_csv_present")
        if submission.get("size", 0) > 0:
            passed_checks.append("submission_csv_nonempty")
        else:
            failed_checks.append("submission_csv_nonempty")
    else:
        failed_checks.append("submission_csv_present")

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
    return review
