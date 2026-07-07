# Agent Entrypoint

This repo is for coding agents operating Kaggle work across sessions.

## First Command

Start every future session with:

```bash
uv run python -m kaggle_agent.cli sessions start --harness <codex|claude|gemini|other> --model <model> --skill <skill-name> --json
uv run python -m kaggle_agent.cli resume-context --json
```

Then choose the workflow from the user's English request.

## User Request Routing

- "Check what happened", "look at updates", "is the submission good or bad" -> use `skills/kaggle-check-updates/SKILL.md`.
- "Find new competitions", "scout Kaggle", "what should we join" -> use `skills/kaggle-scout/SKILL.md`.
- "Plan next experiment", "improve score", "what should we try" -> use `skills/kaggle-next-experiment/SKILL.md`.
- "Review before pushing/submitting" -> read `agents/reviewer.md`.

## Source Of Truth

JSON state is canonical in v0:

- `state/competitions.json`
- `state/profiles.json`
- `state/experiments.json`
- `state/runs.json`
- `state/submissions.json`
- `state/scout_history.json`
- `state/notebooks.json`
- `state/artifacts.json`
- `state/lessons.md`
- `state/observability/sessions.jsonl`

Do not commit `state/`.

Use `tasks add/list/complete` to leave explicit next actions for future sessions.

## Storage Rule

Code, tests, docs, templates, and skills live in Git.

Mutable Kaggle state, data, notebooks, outputs, logs, submissions, and artifacts live outside Git and are synced to Google Drive.

Notebook files should not be committed to this repo. Track notebook identity and Drive/Kaggle references in JSON state.

## Architecture

For the codebase graph and change targets, read `docs/codebase-map.md`.

Personas live in `agents/`. Follow AutoKaggle's roles and phases, adapted for Kaggle remote compute:

- Reader: understands competition rules, metric, data, constraints.
- Planner: picks phase, hypothesis, validation, stop condition.
- Developer: writes notebook/diff for the approved plan.
- Reviewer: blocks repeats, rule risk, leakage, bad validation, invalid submissions.
- Summarizer: records durable lessons.

Kaggle runs are expensive. Register experiments before push and check pending work before planning new work.

## Continuous Self-Correction

This system is meant to compound: every session should leave the repo slightly better than it found it, not just complete the immediate task.

- If you find a bug, wrong assumption, missing check, or outdated instruction anywhere in this repo (code, `agents/*.md`, `skills/*/SKILL.md`, `docs/`, `templates/`) — during normal development or while operating a real Kaggle run — fix it in the repository itself. Do not just work around it for the current run and move on; the next session, on any harness, must not hit the same wall.
- Verify before fixing. Reproduce or confirm the real cause (a live API call, an actual log, the real error) before changing guidance. A confident but unverified "fix" is worse than the original bug, because later sessions will trust it. This has already happened once in this repo: a plausible-but-wrong root-cause guess about Kaggle competition rules got written into `agents/reader.md`, then had to be corrected after actually reproducing the failure with a diagnostic run.
- Record findings where the right future reader will see them, not just in a commit message:
  - Platform/environment/dependency issues (mount paths, package/CUDA mismatches, API quirks) -> append to `state/dev_pitfalls.md`.
  - ML/experiment lessons (what worked, what didn't, why) -> `state/lessons.md`.
  - Process/architecture issues (a skill's steps don't match what the CLI does, a persona is missing a check) -> fix the skill/persona file directly; that edit is the fix, not a note about one.
- This applies across harnesses equally. A fix made by one coding agent (Codex, Claude, Gemini) must be usable by the next, so it belongs in the repo, never only in a conversation transcript.
- Treat any assumption already written into this repo as provisional, not settled — Kaggle's own platform behavior changes over time. When something turns out wrong, correct the file that stated it; don't just patch around it locally and leave the wrong claim in place for the next session to trust.

## End Of Session

Before finishing, append observability:

```bash
uv run python -m kaggle_agent.cli sessions end <session-id> \
  --outcome "<what changed>" \
  --personas orchestrator reviewer summarizer \
  --state-writes runs.json lessons.md \
  --tokens-input <n> \
  --tokens-output <n> \
  --tokens-cache-read <n> \
  --token-source self-report \
  --json
```

If exact token counts are unavailable, use the best available harness-reported value and set `--token-source`.
