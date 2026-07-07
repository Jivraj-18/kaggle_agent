---
name: kaggle-check-updates
description: Use when the user asks to check pending Kaggle notebook runs, inspect submitted work, pull finished outputs, or decide whether recent results are good or bad.
---

# Kaggle Check Updates

Use this skill for user requests like:

- "look at anything new";
- "check what happened";
- "is the submission good or bad";
- "check pending runs";
- "pull outputs".

## Workflow

1. Start an observable session, then load context:
   ```bash
   python -m kaggle_agent.cli sessions start --harness <harness> --model <model> --skill kaggle-check-updates --json
   python -m kaggle_agent.cli resume-context --json
   ```
2. Read pending runs from `state/runs.json`.
3. For each pending run the user asked about, check status once:
   ```bash
   python -m kaggle_agent.cli runs check <run-id> --json
   ```
4. If terminal, pull Kaggle outputs/logs with Kaggle CLI and record artifacts in JSON state.
   ```bash
   python -m kaggle_agent.cli runs pull-output <run-id> --json
   python -m kaggle_agent.cli runs review-output <run-id> --sample-submission <sample_submission.csv> --json
   ```
5. Read `agents/reviewer.md`, `agents/triage.md`, and `agents/summarizer.md` to evaluate:
   - runtime success/failure;
   - `submission.csv` validity;
   - CV/public score movement;
   - rule or leakage risk;
   - whether next action is improve, stop, triage, or submit.
6. Update lessons and sync state:
   ```bash
   python -m kaggle_agent.cli drive-sync push --root state --json
   ```
7. End the session with `python -m kaggle_agent.cli sessions end <session-id> ... --json`.

Do not continuously poll. Check once per user-triggered session unless the user explicitly asks otherwise.
