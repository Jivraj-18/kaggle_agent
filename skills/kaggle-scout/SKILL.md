---
name: kaggle-scout
description: Use when the user asks to find, scout, or evaluate new Kaggle competitions to join. Uses Scout and Orchestrator personas, fetches raw Kaggle rows, and records join/watch/skip decisions.
---

# Kaggle Scout

Triggered by: "find new competitions", "scout Kaggle", "what should we join".

## Workflow

1. Run:
   ```bash
   python -m kaggle_agent.cli sessions start --harness <harness> --model <model> --skill kaggle-scout --json
   python -m kaggle_agent.cli resume-context --json
   ```
2. Read `agents/orchestrator.md` and `agents/scout.md`.
3. Read `state/preferences.json`, `state/lessons.md`, `state/competitions.json`, and latest `state/scout_history.json`.
4. Fetch raw candidates:
   ```bash
   python -m kaggle_agent.cli scout-competitions --groups general community --limit 20 --json
   ```
5. Decide `join`, `watch`, `skip`, or `request-human-review` from raw rows and lessons.
6. Record decisions:
   ```bash
   python -m kaggle_agent.cli competitions add <slug> --decision <decision> --notes "<reason>"
   ```
7. Sync state:
   ```bash
   python -m kaggle_agent.cli drive-sync push --root state --json
   ```
8. End the session with `python -m kaggle_agent.cli sessions end <session-id> ... --json`.
