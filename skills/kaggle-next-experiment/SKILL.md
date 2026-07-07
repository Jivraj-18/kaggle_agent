---
name: kaggle-next-experiment
description: Plan, improve, or continue a Kaggle competition. Use for requests like "plan next experiment", "improve score", "continue this competition", or "what should we try"; routes through Orchestrator, Reader, Planner, Developer, and Reviewer personas and registers experiments before expensive Kaggle runs.
---

# Kaggle Next Experiment

## Workflow

1. Run:
   ```bash
   uv run python -m kaggle_agent.cli sessions start --harness <harness> --model <model> --skill kaggle-next-experiment --json
   uv run python -m kaggle_agent.cli resume-context --json
   ```
2. Read `agents/orchestrator.md`.
3. For the target competition, read relevant persona files:
   - `agents/reader.md`
   - `agents/planner.md`
   - `agents/developer.md`
   - `agents/reviewer.md`
4. Inspect pending runs and prior experiments before planning.
5. Planner proposes exactly one phase, family, hypothesis, validation, stop condition, and `what_changed`.
6. Register before push:
   ```bash
   uv run python -m kaggle_agent.cli experiments add \
     --competition-slug <slug> \
     --phase <phase> \
     --family <family> \
     --what-changed "<material difference>" \
     --hypothesis "<hypothesis>" \
     --plan-file <plan-file> \
     --notebook-file <notebook-file> \
     --status planned \
     --notes "<reason>"
   ```
7. Reviewer must approve before Kaggle push.
8. Validate notebook metadata before push:
   ```bash
   uv run python -m kaggle_agent.cli notebooks validate-metadata <kernel-metadata.json> --competition-slug <slug> --json
   ```
9. Push the approved notebook and register the Kaggle run:
   ```bash
   uv run python -m kaggle_agent.cli notebooks push \
     --path <kernel-dir> \
     --competition-slug <slug> \
     --experiment-key <experiment-key> \
     --kernel-slug <owner/kernel> \
     --version <version> \
     --json
   ```
   If `<kernel-dir>/kernel-metadata.json` exists, this command validates competition source and kernel id before calling Kaggle.
10. End the session. On Claude Code, prefer `sessions end <session-id> --outcome "<summary>" --transcript-file <path-to-.claude/projects/.../SESSION.jsonl> --json` over manual `--tokens-*` (see docs/architecture.md#observability).

Do not push notebooks or submit if Reviewer says `revise`, `stop`, or `escalate`.
