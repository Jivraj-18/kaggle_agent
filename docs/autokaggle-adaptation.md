# AutoKaggle Adaptation

This repo should copy AutoKaggle's operating discipline, not its exact execution model.

## What To Copy

- Six phases: background understanding, preliminary EDA, data cleaning, in-depth EDA, feature engineering, model building/validation/prediction.
- Five roles: Reader, Planner, Developer, Reviewer, Summarizer.
- Reviewer feedback before phase completion.
- Bounded debugging loops.
- Unit-test style gates for data, validation, and submission artifacts.
- Durable reports after each phase.

## What Not To Copy

- Synchronous local execution for heavy ML.
- Assumption that failures return immediately from a Python interpreter.
- Tabular-only tools as the whole system boundary.
- In-memory state.

## Kaggle Version

Kaggle changes the control loop:

```text
plan phase
-> register experiment in JSON
-> local smoke/review gate
-> push notebook
-> wait until user asks to check
-> check status once
-> pull outputs if terminal
-> review logs/submission
-> summarize lessons
-> plan next phase
```

The important architecture invariant is that every expensive Kaggle run must be connected to:

- competition slug;
- AutoKaggle phase;
- hypothesis;
- plan hash;
- notebook hash;
- Kaggle kernel slug/version;
- output/log location;
- CV/LB result when available;
- lesson learned.

## Agent Responsibilities

Reader:

- parse rules, metric, data files, sample submission, constraints;
- produce structured JSON context;
- flag anything requiring human approval.

Planner:

- choose the next AutoKaggle phase;
- state one hypothesis;
- define validation, expected artifact, stop condition, and cost/risk;
- avoid repeating prior experiments.

Developer:

- write the notebook or minimal diff;
- use approved libraries only;
- keep code deterministic;
- write outputs to predictable paths.

Reviewer:

- reject missing hypothesis, weak validation, duplicate experiments, rule risks, bad submission schema, leakage risks, and metric mismatch;
- run cheap local tests before push;
- inspect pulled outputs before submit.

Summarizer:

- record what was tried, what changed, score evidence, failure cause, and next action;
- update durable lessons so future agents do not repeat work.

## Repeat Prevention

The CLI duplicate guard blocks exact repeats through `experiment_key`. The Reviewer must also block semantic repeats:

- same model with only prompt wording changed;
- same validation split under a new experiment name;
- same feature family without a new reason;
- rerun after failure without addressing the failure.

Intentional reruns need `--allow-duplicate` and a clear note explaining why the rerun is useful.
