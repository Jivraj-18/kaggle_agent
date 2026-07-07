---
name: kaggle-scout-new-competitions
description: Use when the user asks to find, scout, or evaluate new Kaggle competitions to join. Fetches raw Kaggle rows and leaves join/watch/skip decisions to the coding agent.
---

# Kaggle Scout New Competitions

Use this skill for user requests like:

- "check new competitions";
- "find competitions we should join";
- "scout Kaggle";
- "what should we try next Saturday".

## Workflow

1. Start with:
   ```bash
   python -m kaggle_agent.cli resume-context --json
   ```
2. Read:
   - `state/preferences.json`
   - `state/lessons.md`
   - `state/competitions.json`
   - latest `state/scout_history.json`
3. Fetch candidates:
   ```bash
   python -m kaggle_agent.cli scout-competitions --groups general community --limit 20 --json
   ```
4. Review `items[].raw` directly. Do not create deterministic ranking functions.
5. Decide `join`, `watch`, `skip`, or `request-human-review`.
6. Record decisions:
   ```bash
   python -m kaggle_agent.cli competitions add <slug> --decision <decision> --notes "<reason>"
   ```
7. Sync state:
   ```bash
   python -m kaggle_agent.cli drive-sync push --root state --json
   ```

The output should explain what raw fields mattered and which prior lessons influenced the decision.
