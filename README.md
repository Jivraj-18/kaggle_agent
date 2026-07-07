# kaggle_agent

Local-first Kaggle automation workspace for coding agents.

The v0 workflow is user-triggered: the user asks the coding agent to scout competitions, check pending Kaggle runs, pull outputs, submit validated notebook outputs, or plan the next experiment. There is no cloud watcher, remote database, Pub/Sub, or notebook callback in v0.

## Core loop

1. Read local state from `state/`.
2. Query Kaggle only for pending or explicitly requested items.
3. Pull outputs/logs only when a run is terminal or state changed.
4. Feed raw Kaggle context and local history to the coding agent for decisions.
5. Use Kaggle as remote compute, not as the source of long-term agent memory.

## Main commands to build

- `kaggle-agent state-summary`: summarize local state.
- `kaggle-agent resume-context`: first command for future coding-agent sessions.
- `kaggle-agent sessions start/end/list`: record session observability and token/cost metadata.
- `kaggle-agent metrics recompute`: regenerate observability roll-ups.
- `kaggle-agent validate-state`: validate state file shapes.
- `kaggle-agent competitions add/list`: record competitions under consideration or joined.
- `kaggle-agent runs add/list/check`: record Kaggle notebook runs and check one run on demand.
- `kaggle-agent submissions add/list`: record submitted files and scores.
- `kaggle-agent scout-competitions`: fetch active competitions and append a raw scout snapshot for coding-agent review.
- `kaggle-agent experiments add/list`: record planned heavy experiments before notebook push and block exact repeats.
- `kaggle-agent drive-sync push`: copy changed local state/data files to Google Drive without deleting history.

Future commands:

- `pull-output`: download output/logs for a completed notebook.
- `plan-next`: use local history to propose the next experiment.

## Design rules

- Do not continuously poll Kaggle unless the user explicitly asks.
- Prefer notebook-output submissions when competition rules care about notebook origin.
- Keep credentials out of git.
- Keep `state/`, generated competition data, and large artifacts out of git by default.
- Archive durable state/data/artifacts in Google Drive when they need to survive beyond this machine. See [docs/google-drive.md](docs/google-drive.md).
- Record why each experiment was attempted, not only the score.
- Keep deterministic code limited to fetching, validation, indexing, and persistence. Competition selection is a coding-agent decision.
- Track `experiment_key` across experiments, runs, and submissions so score changes remain attributable to hypotheses.
- Record session observability in `state/observability/sessions.jsonl`.

## CLI examples

Initialize local state files:

```bash
python -m kaggle_agent.cli init-state
```

Start a coding-agent session:

```bash
python -m kaggle_agent.cli sessions start \
  --harness codex \
  --model gpt-5 \
  --skill kaggle-next-experiment \
  --json
python -m kaggle_agent.cli resume-context --json
```

Record a competition:

```bash
python -m kaggle_agent.cli competitions add heavy-equipment-selling-price-prediction-challenge \
  --title "Heavy Equipment Selling Price Prediction" \
  --decision joined \
  --notes "Tabular regression, RMSLE."
```

Record a Kaggle notebook run:

```bash
python -m kaggle_agent.cli runs add \
  --competition-slug heavy-equipment-selling-price-prediction-challenge \
  --experiment-key <experiment-key> \
  --kernel-slug jivrajsingh/22f3002542-notebook-2026t2 \
  --version 3 \
  --status COMPLETE \
  --outputs-pulled \
  --submitted \
  --next-action improve_score
```

Record a heavy experiment before pushing a notebook:

```bash
python -m kaggle_agent.cli experiments add \
  --competition-slug heavy-equipment-selling-price-prediction-challenge \
  --phase feature_engineering \
  --family feature-gbdt \
  --what-changed "Adds grouped target-safe aggregate features over baseline." \
  --hypothesis "LightGBM with log target and grouped validation improves RMSLE" \
  --plan-file competitions/heavy-equipment/plans/exp001.md \
  --notebook-file competitions/heavy-equipment/notebooks/exp001.py \
  --status planned
```

If the same competition, hypothesis, plan file hash, and notebook file hash already exist, the CLI exits with `duplicate experiment`. Use `--allow-duplicate` only when the repeat is intentional and the reason is recorded in `--notes`.

Check one pending run once:

```bash
python -m kaggle_agent.cli runs check jivrajsingh/22f3002542-notebook-2026t2:v3
```

Pull outputs/logs for a terminal run:

```bash
python -m kaggle_agent.cli runs pull-output jivrajsingh/22f3002542-notebook-2026t2:v3 --json
python -m kaggle_agent.cli runs review-output jivrajsingh/22f3002542-notebook-2026t2:v3 \
  --sample-submission path/to/sample_submission.csv \
  --json
```

Record a submission:

```bash
python -m kaggle_agent.cli submissions add \
  --ref 54414716 \
  --competition-slug heavy-equipment-selling-price-prediction-challenge \
  --experiment-key <experiment-key> \
  --kernel-slug jivrajsingh/22f3002542-notebook-2026t2 \
  --version 3 \
  --public-score 0.21106 \
  --notes "Notebook-output submission."
```

All list/summary commands support `--json` for agent-friendly parsing.

Scout active competitions:

```bash
python -m kaggle_agent.cli scout-competitions --groups general community --limit 20
```

Scouting is intentionally not the decision-maker. The command stores Kaggle's raw rows under `items[].raw` and adds only minimal indexing fields:

- `slug`
- `group`
- `source_index`
- `agent_decision: pending`
- `agent_notes`
- `raw`

The coding agent should read the latest `state/scout_history.json` snapshot, `state/preferences.json`, `state/lessons.md`, and prior competition/run history before making the actual `join/watch/skip/request-human-review` decision. Deterministic code should not score, summarize, or rank competitions in v0.

Scout from saved Kaggle JSON without network access:

```bash
python -m kaggle_agent.cli scout-competitions --from-file /tmp/kaggle-competitions.json --json
```

Push changed local state files to Google Drive:

```bash
python -m kaggle_agent.cli drive-sync push --json
```

Recompute observability roll-ups:

```bash
python -m kaggle_agent.cli metrics recompute --json
```
