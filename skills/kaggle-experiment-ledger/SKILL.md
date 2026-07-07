---
name: kaggle-experiment-ledger
description: Use before planning or pushing heavy Kaggle notebook experiments. Registers JSON experiment records, blocks exact repeats, and forces the agent to inspect pending work before spending Kaggle compute.
---

# Kaggle Experiment Ledger

JSON state remains canonical in v0.

## Preflight

Run or read:

```bash
python -m kaggle_agent.cli state-summary --json
python -m kaggle_agent.cli experiments list --competition-slug <slug> --json
python -m kaggle_agent.cli runs list --pending --json
```

Also read `state/lessons.md` and relevant output logs.

## Register Before Push

```bash
python -m kaggle_agent.cli experiments add \
  --competition-slug <slug> \
  --hypothesis "<specific hypothesis>" \
  --plan-file <plan-file> \
  --notebook-file <notebook-file> \
  --status planned \
  --notes "<phase and why this is not a repeat>"
```

If the command exits with `duplicate experiment`, stop and inspect the existing record.

Use `--allow-duplicate` only for intentional reruns such as infrastructure failure, seed confirmation, or reproducibility checks. Explain the reason in `--notes`.

## Semantic Repeat Check

The CLI blocks exact repeats. The agent must block semantic repeats:

- same hypothesis with renamed files;
- same notebook with cosmetic changes;
- same validation split with no new learning;
- rerun after an error without addressing the error.
