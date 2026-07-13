# ML Engineer Agent Architecture

This repo is a local-first Kaggle automation workspace. Kaggle provides remote notebook execution; the local repo is the durable memory, planning surface, and audit trail.

## Principles

- Keep decisions with the coding agent, not hidden scoring functions.
- Keep JSON state as the agent-facing source of truth in v0.
- Preserve raw Kaggle rows, rules, files, logs, notebook outputs, and scores.
- Run ML training on Kaggle unless a local smoke test is cheap and bounded.
- Audit high-ranked public notebooks after joining; reproduce the strongest compliant candidate before planning original improvements.
- Query Kaggle only when the user asks or when a known pending item is being checked.
- Never make official submissions without an explicit human review step.
- Keep code in GitHub and mutable state/data/artifacts in Google Drive.

## AutoKaggle Adaptation

AutoKaggle's useful core is not its exact runtime. Its useful core is the discipline:

1. background understanding;
2. preliminary EDA;
3. data cleaning;
4. in-depth EDA;
5. feature engineering;
6. model building, validation, and prediction.

What this repo copies from AutoKaggle: the six phases above; the five roles (Reader, Planner, Developer, Reviewer, Summarizer); Reviewer feedback before phase completion; bounded debugging loops; unit-test style gates for data, validation, and submission artifacts; durable reports after each phase.

What this repo does not copy: synchronous local execution for heavy ML; the assumption that failures return immediately from a Python interpreter; tabular-only tools as the whole system boundary; in-memory state.

AutoKaggle runs synchronously in a local Python interpreter. This repo cannot copy that directly because Kaggle notebooks run remotely and asynchronously. The adaptation is:

- every phase becomes an experiment record in JSON state;
- the Developer writes Kaggle notebook code instead of executing heavy code locally;
- the Reviewer gate runs before notebook push and again after output pull;
- the Summarizer writes durable JSON/Markdown lessons after each phase;
- Kaggle status/output replaces AutoKaggle's immediate interpreter feedback.

The architecture goal is controlled iteration, not one-shot notebook generation.

## V0 Loop

1. `scout-competitions` fetches active Kaggle competitions and appends raw snapshots to `state/scout_history.json`.
2. The coding agent reads raw scout data, `state/preferences.json`, `state/lessons.md`, prior competitions, runs, and submissions.
3. The agent decides `join`, `watch`, `skip`, or `request-human-review` and records the decision.
4. For a chosen competition, the agent snapshots rules, metric, files, sample submission, notebook constraints, and discussion notes.
5. `notebooks discover-public` records a score-ordered public shortlist and optionally pulls a few sources for text-only audit.
6. Planner and Reviewer select the highest-ranked compliant, reproducible candidate; unsafe higher-ranked candidates get explicit rejection reasons.
7. The agent reproduces that source as a baseline-only experiment under the repo's validation protocol, then creates EDA findings from its predictions before planning improvements.
8. The agent writes each later plan as one measured delta from the accepted baseline, with a finding ID, validation method, stop condition, and compliance notes.
9. Before any heavy run, the agent records the experiment in `state/experiments.json` with hypothesis, plan hash, notebook hash, status, and intended run link.
10. The notebook developer creates or edits a Kaggle notebook and local smoke tests the notebook structure before push.
11. `kaggle kernels push` starts the Kaggle run. The local state records notebook slug, version, source hash, metadata, and next action.
12. The user later asks the agent to check pending work. The agent checks status once, pulls outputs only for terminal runs, and records logs/artifacts.
13. The reviewer validates `submission.csv`, compares CV and leaderboard evidence, records lessons, and asks for human approval before official submit.
14. `drive-sync push` copies changed local state/data files to Google Drive without deleting old history.

## Experiment Memory

Heavy experiments must be registered before notebook push:

```bash
uv run python -m kaggle_agent.cli experiments add \
  --competition-slug <slug> \
  --hypothesis "<specific hypothesis>" \
  --plan-file <plan.md> \
  --notebook-file <notebook.py> \
  --status planned
```

The CLI computes an `experiment_key` from competition slug, normalized hypothesis, plan file hash, and notebook file hash. If that key already exists, the command fails with `duplicate experiment`. This is an indexing guard, not an ML decision-maker: the coding agent still decides whether a similar-but-not-identical experiment is worthwhile.

The guard only blocks exact repeats. The Reviewer must also block semantic repeats:

- same model with only prompt wording changed;
- same validation split under a new experiment name;
- same feature family without a new reason;
- rerun after failure without addressing the failure.

Intentional reruns need `--allow-duplicate` and a clear note explaining why the rerun is useful.

Before planning new work, future agents must read:

- `state/notebooks.json`, including the selected public baseline and its review notes
- `state/experiments.json`
- `state/runs.json`
- `state/submissions.json`
- `state/lessons.md`
- the latest pulled notebook outputs and logs for the target competition

The default stance is no repeated heavy experiment unless the agent can explain what changed and records that reason.

## Roles

Persona files live in `agents/`.

- Reader: builds competition/profile context from rules, metric, files, data shape, and constraints.
- Planner: audits public baseline candidates, then chooses the AutoKaggle phase, hypothesis, validation plan, and stop condition.
- Developer: writes notebook code or notebook diffs for exactly the approved plan.
- Reviewer: blocks weak plans, invalid submissions, leakage risks, metric mismatch, and repeated churn.
- Summarizer: records durable lessons and phase reports.
- Kaggle Triage: classifies remote notebook errors and routes back to Planner/Developer/Reviewer.
- Scout: fetches raw competition candidates and discussion pointers before Reader starts.

V0 can run these roles as prompts inside one coding-agent session. Separate subagents are useful for isolated review, live Kaggle checks, and long-context research, but the filesystem remains the shared blackboard.

## Phase Records

Each significant attempt should map to one AutoKaggle phase:

```json
{
  "competition_slug": "example",
  "phase": "feature_engineering",
  "hypothesis": "Frequency encoding high-cardinality categoricals improves grouped CV.",
  "status": "planned",
  "plan_sha256": "...",
  "notebook_sha256": "...",
  "experiment_key": "..."
}
```

Recommended phase values:

```text
background_understanding
preliminary_eda
data_cleaning
in_depth_eda
feature_engineering
model_building_validation_prediction
triage_fix
submission_review
```

This keeps AutoKaggle's phase decomposition while preserving JSON as the agent-facing state.

## Observability

Each coding-agent session should be recorded:

```bash
uv run python -m kaggle_agent.cli sessions start --harness <harness> --model <model> --skill <skill> --json
uv run python -m kaggle_agent.cli sessions end <session-id> --outcome "<summary>" --tokens-input <n> --tokens-output <n> --json
```

On Claude Code, prefer parsing real usage from the transcript over self-reporting:

```bash
uv run python -m kaggle_agent.cli sessions end <session-id> --outcome "<summary>" \
  --transcript-file ~/.claude/projects/<project-slug>/<claude-session-uuid>.jsonl --json
```

The Claude Code session UUID is the directory segment before `/scratchpad` in the scratchpad path given in the system prompt. `--transcript-file` overrides `--tokens-*` and sets `tokens.source` to `claude-transcript-parse`. Codex/Gemini transcript parsers are not built yet; use `--tokens-*` with `--token-source self-report` for those harnesses.

Use `experiment_key` to join:

- `experiments.json`
- `runs.json`
- `submissions.json`

Regenerate roll-ups with:

```bash
uv run python -m kaggle_agent.cli metrics recompute --json
```

## Output Ingestion

Terminal Kaggle runs should be pulled into ignored local artifacts and recorded in `state/artifacts.json`:

```bash
uv run python -m kaggle_agent.cli runs pull-output <run-id> --json
```

The artifact record joins to runs and experiments through `run_id` and `experiment_key`. Reviewer, Triage, and Summarizer use this record to decide whether the result is good, bad, invalid, or worth submitting.

## State Machine

```text
competition_discovered
-> competition_profile_built
-> public_baselines_audited
-> public_baseline_selected
-> baseline_planned
-> experiment_registered
-> local_smoke_test_passed
-> notebook_generated
-> notebook_pushed
-> notebook_running
-> notebook_completed
-> outputs_pulled
-> validation_analyzed
-> human_submit_approved
-> submitted
-> leaderboard_recorded
-> next_experiment_planned
```

Failure states:

```text
runtime_error
invalid_submission
quota_exhausted
metric_mismatch
suspected_leakage
rule_violation_risk
repeated_no_improvement
human_review_required
stopped
```

## What Not To Build Yet

- Cloud Functions, Pub/Sub, remote database, or always-on watcher.
- Email-triggered orchestration.
- Deterministic competition scoring that hides raw Kaggle context from the agent.
- Vector database memory before raw files and lessons are useful.
- Multi-competition parallel execution before one competition loop is reliable.
