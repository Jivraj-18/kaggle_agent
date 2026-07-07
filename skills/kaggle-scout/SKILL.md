---
name: kaggle-scout
description: Find, scout, or evaluate new Kaggle competitions to join. Use for requests like "find new competitions", "scout Kaggle", "what should we join", or weekly competition discovery; uses Scout and Orchestrator personas, fetches raw Kaggle rows, and records join/watch/skip decisions.
---

# Kaggle Scout

## Workflow

1. Run:
   ```bash
   uv run python -m kaggle_agent.cli sessions start --harness <harness> --model <model> --skill kaggle-scout --json
   uv run python -m kaggle_agent.cli resume-context --json
   ```
2. Read `agents/orchestrator.md` and `agents/scout.md`.
3. Read `state/preferences.json`, `state/lessons.md`, `state/competitions.json`, and latest `state/scout_history.json`.
4. Fetch raw candidates. `--limit` applies per group (each requested group returns up to `--limit` items), not to the combined total:
   ```bash
   uv run python -m kaggle_agent.cli scout-competitions --groups general community --limit 20 --json
   ```
5. Decide `join`, `watch`, `skip`, or `request-human-review` from raw rows and lessons.
6. Record decisions:
   ```bash
   uv run python -m kaggle_agent.cli competitions add <slug> --decision <decision> --notes "<reason>"
   ```
7. Sync state:
   ```bash
   uv run python -m kaggle_agent.cli drive-sync push --root state --json
   ```
8. End the session. On Claude Code, prefer `sessions end <session-id> --outcome "<summary>" --transcript-file <path-to-.claude/projects/.../SESSION.jsonl> --json` over manual `--tokens-*` (see docs/architecture.md#observability).
