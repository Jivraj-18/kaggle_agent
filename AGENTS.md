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

Before writing notebook code, read `.claude/skills/kaggle-api-capabilities/SKILL.md` (a plain file — works on any harness) for verified Kaggle kernel resource limits and stdout parsing quirks.

## Continuous Self-Correction

Every session should leave the repo better, not just finish the task.

- Found a bug, wrong assumption, or gap in code, `agents/`, `skills/`, `docs/`, or `templates/`? Fix it in the repo, not just for this run.
- Verify before fixing — reproduce the real cause first. A confident but wrong fix is worse than the bug (it already happened once: a guess about Kaggle rules got written into `agents/reader.md`, then had to be corrected).
- Record it where it'll be read: platform/environment issues -> `state/dev_pitfalls.md`; ML lessons -> `state/lessons.md`; process/architecture issues -> fix the skill/persona file directly.
- Applies across harnesses (Codex/Claude/Gemini) — a fix belongs in the repo, not only a transcript.
- Keep entries short: the fact and the fix, not a narrated investigation.
- Before adding an entry anywhere (`state/dev_pitfalls.md`, `state/lessons.md`, persona/skill docs), check if an existing one already covers it. If so, edit that entry in place — correct, tighten, or extend it — instead of appending a new one. Only add a new entry for something genuinely new. These files should stay curated, not just grow.

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

Also run `uv run python -m kaggle_agent.cli prompt-history sync-claude --json` (Claude Code) or `sync-codex` (Codex) before finishing. Both harnesses have a live `UserPromptSubmit` hook too, but a live hook firing "successfully" doesn't guarantee it logged anything — one already had a silent race-condition bug that only showed up on real use (see docs/state-schemas.md) — so treat the manual sync as the guaranteed path regardless. Logs to `state/prompt_history.md`, each session with its harness's resume command.
