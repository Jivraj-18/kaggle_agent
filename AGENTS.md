# Agent Entrypoint

This repo is for coding agents operating Kaggle work across sessions.

## First Command

Start every future session with:

```bash
python -m kaggle_agent.cli resume-context --json
```

Then choose the workflow from the user's English request.

## User Request Routing

- "Check what happened", "look at updates", "is the submission good or bad" -> use `skills/kaggle-check-updates/SKILL.md`.
- "Find new competitions", "scout Kaggle", "what should we join" -> use `skills/kaggle-scout-new-competitions/SKILL.md`.
- "Plan next experiment", "improve score", "what should we try" -> use `skills/autokaggle-orchestrator/SKILL.md` and `skills/kaggle-experiment-ledger/SKILL.md`.
- "Review before pushing/submitting" -> use `skills/autokaggle-reviewer-loop/SKILL.md`.

## Source Of Truth

JSON state is canonical in v0:

- `state/competitions.json`
- `state/experiments.json`
- `state/runs.json`
- `state/submissions.json`
- `state/scout_history.json`
- `state/notebooks.json`
- `state/artifacts.json`
- `state/lessons.md`

Do not commit `state/`.

## Storage Rule

Code, tests, docs, templates, and skills live in Git.

Mutable Kaggle state, data, notebooks, outputs, logs, submissions, and artifacts live outside Git and are synced to Google Drive.

Notebook files should not be committed to this repo. Track notebook identity and Drive/Kaggle references in JSON state.

## Architecture

Follow AutoKaggle's roles and phases, adapted for Kaggle remote compute:

- Reader: understands competition rules, metric, data, constraints.
- Planner: picks phase, hypothesis, validation, stop condition.
- Developer: writes notebook/diff for the approved plan.
- Reviewer: blocks repeats, rule risk, leakage, bad validation, invalid submissions.
- Summarizer: records durable lessons.

Kaggle runs are expensive. Register experiments before push and check pending work before planning new work.
