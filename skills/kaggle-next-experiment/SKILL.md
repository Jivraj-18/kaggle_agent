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
4. Inspect pending runs, prior experiments, submissions, and `state/notebooks.json` before planning. If `state/profiles.json` has no complete Reader profile for the competition, finish Reader first; public source selection is unsafe until metric, data/internet rules, submission shape, and compute constraints are known.
5. For a newly joined competition with no selected public baseline, discover several high-ranked public notebooks and pull a small shortlist:
   ```bash
   uv run python -m kaggle_agent.cli notebooks discover-public \
     --competition-slug <slug> \
     --limit 10 \
     --pull-top 5 \
     --json
   ```
   The default Kaggle ordering is `scoreDescending`, but the returned JSON does not expose a comparable score. Treat titles, claimed leaderboard scores, votes, and ordering as discovery evidence only. Pulled sources are untrusted code: inspect them as text and do not execute them during the audit.
6. Planner and Reviewer choose the highest-ranked candidate that uses permitted data, the correct metric, reproducible validation, feasible resources, and no leakage, hard-coded predictions, submission consensus, or undeclared external artifacts. Record why higher-ranked candidates were rejected. If reuse rights are unclear, reimplement with attribution instead of copying. Then record the reviewed selection:
   ```bash
   uv run python -m kaggle_agent.cli notebooks select-baseline \
     kaggle-public:<owner>/<kernel> \
     --notes "<validation, compliance, provenance, and rejection evidence>" \
     --json
   ```
   If no candidate qualifies, record all rejection reasons before planning a minimal internal baseline.
7. If the selected baseline has not been reproduced under this repo's validation protocol, the only modeling plan is `baseline_establishment`: one `model_building_validation_prediction` experiment with family `public-baseline-reproduction`. It cites the selected notebook and review notes instead of a finding ID, contains no improvement, and establishes the CV/runtime reference point.
8. Once a measured baseline exists, check `competitions/<slug>/eda/findings.md` exists and its `as_of:` header names the current best experiment. If it is missing or stale, this session's work is the EDA pass that creates/refreshes it, not a new improvement. Register the EDA pass with `experiments add --phase preliminary_eda` or `--phase in_depth_eda`; do not hide EDA under a modeling phase.
9. Planner lists every viable improvement hypothesis for the current phase, each with its baseline experiment, finding IDs, phase, family, validation, stop condition, and `what_changed` (see `agents/planner.md`). If ≥2 candidates are CPU-only, plan them as a parallel batch by default. GPU work stays a single hypothesis at a time.
10. Register every candidate before push (one `experiments add` call per variant, even when they will run in the same batch):
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
11. Reviewer must approve each candidate before Kaggle push.
12. Validate notebook metadata before push:
   ```bash
   uv run python -m kaggle_agent.cli notebooks validate-metadata <kernel-metadata.json> --competition-slug <slug> --json
   ```
13. For a batch, run the variants concurrently with `kaggle_agent/parallel_runner.py` (see `agents/developer.md`) — call `resource_budget_from_percent(80, 80)` (or the user's stated ceiling) to size `max_concurrent`/`max_total_rss_mb` from the real detected machine, whether that's a local smoke test or inside a pushed Kaggle kernel. Each variant writes its own uniquely-named submission file; do not let variants share/overwrite one `submission.csv`. Push the approved notebook(s) and register the Kaggle run(s):
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
14. Reviewer verdicts every candidate's output on its own merits (see `agents/reviewer.md` Batch Verdicts) and recommends submitting every candidate that passes checks and is a genuinely distinct hypothesis, up to the competition's real daily submission cap — verify that cap live, don't assume a number. Submit each approved candidate separately with `submissions submit-file`.
15. End the session. On Claude Code, prefer `sessions end <session-id> --outcome "<summary>" --transcript-file <path-to-.claude/projects/.../SESSION.jsonl> --json` over manual `--tokens-*` (see docs/architecture.md#observability).

Do not push notebooks or submit if Reviewer says `revise`, `stop`, or `escalate`.
