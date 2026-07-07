---
name: autokaggle-reviewer-loop
description: Use before pushing Kaggle notebooks or accepting experiment results. Implements AutoKaggle's Reviewer discipline for duplicate detection, rules, validation, submission schema, leakage, and bounded retry loops.
---

# AutoKaggle Reviewer Loop

Use this skill as the gate before notebook push and before official submission.

## Before Push

Block the push unless all are true:

- experiment is registered in `state/experiments.json`;
- hypothesis is specific;
- phase is clear;
- validation method matches the metric and data structure;
- rules/internet/external-data settings are explicit;
- exact duplicate guard passed;
- semantic repeat was reviewed;
- local smoke tests pass.

## After Pull

Inspect:

- notebook status and logs;
- output files;
- `submission.csv` shape and columns;
- local CV/validation score;
- public leaderboard result when available;
- lessons learned.

## Retry Rules

- Runtime error: triage once, patch minimally, rerun only if cause is addressed.
- Invalid submission: block submission, fix schema first.
- Metric mismatch: return to Reader/Planner.
- Suspected leakage: stop and require human review.
- Repeated no improvement: prune branch or change phase.
- Quota risk: stop until user approves.

Do not let the agent generate a new notebook just because a previous run failed. It must state what changed.
