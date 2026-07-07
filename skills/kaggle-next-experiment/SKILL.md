---
name: kaggle-next-experiment
description: Use when the user asks to plan, improve, or continue a Kaggle competition. Routes through Orchestrator, Reader, Planner, Developer, and Reviewer personas; registers experiments before expensive Kaggle runs.
---

# Kaggle Next Experiment

Triggered by: "plan next experiment", "improve score", "continue this competition".

## Workflow

1. Run:
   ```bash
   python -m kaggle_agent.cli sessions start --harness <harness> --model <model> --skill kaggle-next-experiment --json
   python -m kaggle_agent.cli resume-context --json
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
   python -m kaggle_agent.cli experiments add \
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
8. End the session with `python -m kaggle_agent.cli sessions end <session-id> ... --json`.

Do not push notebooks or submit if Reviewer says `revise`, `stop`, or `escalate`.
