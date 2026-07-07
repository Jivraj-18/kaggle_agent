---
name: autokaggle-orchestrator
description: Use when operating this Kaggle agent repo through AutoKaggle-style phases. Keeps JSON state canonical, maps work to Reader/Planner/Developer/Reviewer/Summarizer roles, and treats Kaggle as asynchronous remote compute.
---

# AutoKaggle Orchestrator

Use this skill before planning Kaggle work in this repo.

## Required Reads

Read these first:

- `docs/autokaggle-adaptation.md`
- `docs/ml-engineer-agent-architecture.md`
- `state/experiments.json`
- `state/runs.json`
- `state/submissions.json`
- `state/lessons.md`

## Phase Order

Use AutoKaggle phases:

1. `background_understanding`
2. `preliminary_eda`
3. `data_cleaning`
4. `in_depth_eda`
5. `feature_engineering`
6. `model_building_validation_prediction`

Do not jump to advanced modeling until the earlier phase evidence exists or the reason is explicit.

## Execution Loop

1. Reader builds/updates competition context.
2. Planner selects exactly one phase and one hypothesis.
3. Register the experiment in JSON before heavy work.
4. Developer writes notebook/diff for that plan only.
5. Reviewer checks rules, duplicate risk, local smoke tests, metric, and submission format.
6. Push to Kaggle only after review passes.
7. Later, check status once when user asks.
8. Pull terminal outputs, summarize lessons, and update JSON state.

Kaggle is remote compute. Local execution is for bounded smoke tests only.
