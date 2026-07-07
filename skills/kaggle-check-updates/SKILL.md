---
name: kaggle-check-updates
description: Check pending Kaggle notebook runs, inspect submitted work, pull finished outputs, and decide whether recent results are good or bad. Use for requests like "look at anything new", "check what happened", "is the submission good or bad", "check pending runs", or "pull outputs".
---

# Kaggle Check Updates

## Workflow

1. Start an observable session, then load context:
   ```bash
   uv run python -m kaggle_agent.cli sessions start --harness <harness> --model <model> --skill kaggle-check-updates --json
   uv run python -m kaggle_agent.cli resume-context --json
   ```
2. Read pending runs from `state/runs.json`.
3. For each pending run the user asked about, check status once:
   ```bash
   uv run python -m kaggle_agent.cli runs check <run-id> --json
   ```
4. If terminal, pull Kaggle outputs/logs with Kaggle CLI and record artifacts in JSON state.
   ```bash
   uv run python -m kaggle_agent.cli runs pull-output <run-id> --json
   uv run python -m kaggle_agent.cli runs review-output <run-id> --sample-submission <sample_submission.csv> --json
   ```
5. Read `agents/reviewer.md`, `agents/triage.md`, and `agents/summarizer.md` to evaluate:
   - runtime success/failure;
   - `submission.csv` validity;
   - CV/public score movement;
   - rule or leakage risk;
   - whether next action is improve, stop, triage, or submit.
6. If Reviewer approves an official CSV submission and the user has approved submitting, upload the reviewed file without rerunning the notebook:
   ```bash
   uv run python -m kaggle_agent.cli submissions submit-file \
     --competition-slug <slug> \
     --file <path/to/submission.csv> \
     --message "<experiment/run summary>" \
     --experiment-key <experiment-key> \
     --kernel-slug <owner/kernel> \
     --version <version> \
     --json
   ```
7. If a prior run has `next_action: check_leaderboard`, refresh Kaggle submission scores:
   ```bash
   uv run python -m kaggle_agent.cli submissions refresh --competition-slug <slug> --json
   ```
8. Update lessons and sync state:
   ```bash
   uv run python -m kaggle_agent.cli drive-sync push --root state --json
   ```
9. End the session. On Claude Code, prefer `sessions end <session-id> --outcome "<summary>" --transcript-file <path-to-.claude/projects/.../SESSION.jsonl> --json` over manual `--tokens-*` (see docs/architecture.md#observability).

Do not continuously poll. Check once per user-triggered session unless the user explicitly asks otherwise.
