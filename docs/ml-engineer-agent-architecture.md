# ML Engineer Agent Architecture

This repo is a local-first Kaggle automation workspace. Kaggle provides remote notebook execution; the local repo is the durable memory, planning surface, and audit trail.

## Principles

- Keep decisions with the coding agent, not hidden scoring functions.
- Preserve raw Kaggle rows, rules, files, logs, notebook outputs, and scores.
- Run ML training on Kaggle unless a local smoke test is cheap and bounded.
- Query Kaggle only when the user asks or when a known pending item is being checked.
- Never make official submissions without an explicit human review step.
- Keep code in GitHub and mutable state/data/artifacts in Google Drive.

## V0 Loop

1. `scout-competitions` fetches active Kaggle competitions and appends raw snapshots to `state/scout_history.json`.
2. The coding agent reads raw scout data, `state/preferences.json`, `state/lessons.md`, prior competitions, runs, and submissions.
3. The agent decides `join`, `watch`, `skip`, or `request-human-review` and records the decision.
4. For a chosen competition, the agent snapshots rules, metric, files, sample submission, notebook constraints, and discussion notes.
5. The agent writes a plan with a named hypothesis, expected artifact, validation method, stop condition, and compliance notes.
6. The notebook developer creates or edits a Kaggle notebook and local smoke tests the notebook structure before push.
7. `kaggle kernels push` starts the Kaggle run. The local state records notebook slug, version, source hash, metadata, and next action.
8. The user later asks the agent to check pending work. The agent checks status once, pulls outputs only for terminal runs, and records logs/artifacts.
9. The reviewer validates `submission.csv`, compares CV and leaderboard evidence, records lessons, and asks for human approval before official submit.
10. `drive-sync push` copies changed local state/data files to Google Drive without deleting old history.

## Roles

- Scout: fetch raw competition candidates and discussion pointers.
- Reader: build competition profile from rules, metric, files, data shape, and constraints.
- Planner: choose the next hypothesis and stop condition from raw context and prior lessons.
- Developer: write notebook code and keep it compatible with competition rules.
- Reviewer: block weak plans, invalid submissions, leakage risks, metric mismatch, and repeated churn.
- Triage: classify notebook errors and decide whether to fix, retry, or escalate.
- Summarizer: write durable lessons that future agents can reuse.

V0 can run these roles as prompts inside one coding-agent session. Separate subagents are useful for isolated review, live Kaggle checks, and long-context research, but the filesystem remains the shared blackboard.

## State Machine

```text
competition_discovered
-> competition_profile_built
-> baseline_planned
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
