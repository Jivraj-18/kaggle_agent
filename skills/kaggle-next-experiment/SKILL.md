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
4. Inspect pending runs and prior experiments before planning. Check `competitions/<slug>/eda/findings.md` exists and its `as_of:` header names the current best experiment. If it's missing or `as_of` names a stale experiment, this session's work is the EDA pass that creates/refreshes it — not a new modeling experiment (see `agents/planner.md`). Register that EDA pass itself with `experiments add --phase preliminary_eda` (first findings.md for this competition) or `--phase in_depth_eda` (residual/importance/segmentation work on an existing best model) — not just `feature_engineering`/`model_building_validation_prediction`. `state/experiments.json`'s phase field only reflects real work if EDA passes are actually registered under it; skipping registration silently makes those two phases unreachable in state history even though findings.md exists on disk (found live — see `docs/architecture.md`#observability).
5. Planner lists every viable candidate hypothesis for the current phase, each with its own phase, family, hypothesis, validation, stop condition, and `what_changed` (see `agents/planner.md`). If ≥2 candidates are CPU-only, plan them as a parallel batch by default — do not pick one and shelve the rest "for later" without a reason. GPU work stays a single hypothesis at a time.
6. Register every candidate before push (one `experiments add` call per variant, even when they'll run in the same batch):
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
7. Reviewer must approve each candidate before Kaggle push.
8. Validate notebook metadata before push:
   ```bash
   uv run python -m kaggle_agent.cli notebooks validate-metadata <kernel-metadata.json> --competition-slug <slug> --json
   ```
9. For a batch, run the variants concurrently with `kaggle_agent/parallel_runner.py` (see `agents/developer.md`) — call `resource_budget_from_percent(80, 80)` (or the user's stated ceiling) to size `max_concurrent`/`max_total_rss_mb` from the real detected machine, whether that's a local smoke test or inside a pushed Kaggle kernel. Each variant writes its own uniquely-named submission file; do not let variants share/overwrite one `submission.csv`. Push the approved notebook(s) and register the Kaggle run(s):
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
10. Reviewer verdicts every candidate's output on its own merits (see `agents/reviewer.md` Batch Verdicts) and recommends submitting every candidate that passes checks and is a genuinely distinct hypothesis, up to the competition's real daily submission cap — verify that cap live, don't assume a number. Submit each approved candidate separately with `submissions submit-file`.
11. End the session. On Claude Code, prefer `sessions end <session-id> --outcome "<summary>" --transcript-file <path-to-.claude/projects/.../SESSION.jsonl> --json` over manual `--tokens-*` (see docs/architecture.md#observability).

Do not push notebooks or submit if Reviewer says `revise`, `stop`, or `escalate`.
