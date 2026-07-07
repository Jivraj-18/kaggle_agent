# State Schemas

JSON state is canonical in v0. Files under `state/` are ignored by Git and synced to Google Drive.

## Join Keys

Use these keys to connect records:

- `competition_slug`: competition identity.
- `experiment_key`: hypothesis/plan/notebook identity.
- `run_id`: Kaggle notebook run identity.
- `submission_ref`: Kaggle submission identity.
- `session_id`: coding-agent session identity.

## experiments.json

Required for heavy runs:

```json
{
  "experiment_id": "slug-20260707T120000Z",
  "competition_slug": "example",
  "phase": "feature_engineering",
  "family": "feature-gbdt",
  "what_changed": "Adds frequency encoding over baseline.",
  "hypothesis": "Frequency encoding improves grouped CV.",
  "experiment_key": "sha256",
  "plan_file": "competitions/example/plans/001.md",
  "notebook_file": "notebooks/example-001.py",
  "plan_sha256": "sha256",
  "notebook_sha256": "sha256",
  "status": "planned",
  "run_id": null,
  "cv_score": null,
  "cv_baseline": null,
  "lb_score": null,
  "outcome": null,
  "notes": ""
}
```

Recommended phase values:

```text
background_understanding
preliminary_eda
data_cleaning
in_depth_eda
feature_engineering
model_building_validation_prediction
triage_fix
submission_review
```

## runs.json

```json
{
  "run_id": "owner/kernel:v1",
  "competition_slug": "example",
  "experiment_key": "sha256",
  "kernel_slug": "owner/kernel",
  "version": 1,
  "status": "running",
  "failure_class": null,
  "outputs_pulled": false,
  "submitted": false,
  "next_action": "check_status",
  "notes": ""
}
```

## submissions.json

```json
{
  "submission_ref": "123",
  "competition_slug": "example",
  "experiment_key": "sha256",
  "kernel_slug": "owner/kernel",
  "version": 1,
  "file_name": "submission.csv",
  "status": "COMPLETE",
  "valid": true,
  "cv_score": 0.75,
  "public_score": 0.8,
  "private_score": null,
  "rank": 100,
  "percentile": 0.9,
  "notes": ""
}
```

## observability/sessions.jsonl

Append one completed session record per coding-agent session:

```json
{"session_id":"20260707T120000Z-codex","harness":"codex","model":"gpt-5","skill_invoked":"kaggle-check-updates","competition_slug":"example","started_at":"2026-07-07T12:00:00Z","ended_at":"2026-07-07T12:10:00Z","personas_used":["reviewer","summarizer"],"state_writes":["runs.json","lessons.md"],"outcome":"checked_pending_runs","human_interventions":0,"tokens":{"input":1000,"output":200,"cache_read":300,"source":"self-report"},"estimated_cost_usd":0.12}
```

Use `sessions start` and `sessions end`; do not hand-edit JSONL.

## artifacts.json

Kaggle outputs and pulled logs are recorded here:

```json
{
  "artifact_id": "owner/kernel:v1-output-20260707T120000Z",
  "run_id": "owner/kernel:v1",
  "competition_slug": "example",
  "experiment_key": "sha256",
  "kind": "kaggle_output",
  "source": "kaggle_cli",
  "local_path": "artifacts/example/owner__kernel__v1",
  "files": [
    {
      "name": "submission.csv",
      "size": 1234,
      "sha256": "sha256"
    }
  ],
  "review": {
    "verdict": "submission_candidate",
    "next_action": "human_review_submission",
    "passed_checks": ["submission_csv_present", "submission_csv_nonempty"],
    "failed_checks": [],
    "reviewed_at": "2026-07-07T12:01:00Z"
  },
  "created_at": "2026-07-07T12:00:00Z"
}
```

Use:

```bash
python -m kaggle_agent.cli runs pull-output <run-id> --json
python -m kaggle_agent.cli runs review-output <run-id> --json
```
