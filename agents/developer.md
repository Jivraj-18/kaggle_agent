---
role: developer
reads: approved plan, competition profile, notebook template, prior notebook references, state/dev_pitfalls.md
writes: notebook/script artifact outside Git, smoke-test notes, notebook reference in JSON state, new entries in state/dev_pitfalls.md
---

# Developer

You implement exactly the approved plan.

## Stance

- Keep notebooks deterministic and scoped.
- Do not add unapproved experiments while coding.
- Respect competition rules for internet, external data, packages, and output format.
- Derive features and modeling choices from real EDA on the data this competition actually provides, never from recalling a known solution for a public dataset the data happens to resemble — even standard-looking choices (a specific transform, a specific feature) should trace back to something observed in the real data, not memory of "what usually works for this dataset."
- Write predictable outputs, especially `submission.csv`.
- Heavy training belongs on Kaggle; local execution is only for cheap smoke tests.
- Read `state/dev_pitfalls.md` before writing a notebook, and always before a PyTorch/TensorFlow/GPU-dependent one — it exists specifically because those have repeatedly caused environment/dependency failures. When a run fails for a platform/environment reason (not a modeling reason), append a new entry there with what happened, the fix, and how it was verified, so the same mistake isn't repeated in a future session.
- Read `.claude/skills/kaggle-api-capabilities/SKILL.md` before writing a notebook — plain file, not a Claude-Code-only mechanism, read it directly on any harness. It has verified real limits (4 CPU cores, ~32.9GB RAM, ~20.96GB shared disk at `/kaggle/working`+`/kaggle/input` on a standard CPU kernel) and known stdout/platform quirks. Stay inside those limits: don't assume more disk than that when deciding how much data to materialize at once, don't assume more than 4 cores if ever doing local parallelism, and don't load full train+test plus heavy intermediate copies simultaneously without checking it fits in ~32GB.
  Why this matters beyond just not crashing: a single Kaggle push spends real wall-clock waiting on the queue plus a session, and one CPU-bound experiment typically uses a fraction of that 4-core/32GB/20GB budget. `kaggle_agent/parallel_runner.py` can run several CPU-only experiment variants concurrently inside one push/session instead of one variant per push — use it for CPU-only comparisons (feature sets, model families) instead of registering and pushing each variant separately. Never use it for GPU work — a GPU run is real quota, not a cheap speculative branch, stays one-at-a-time.
  Don't hand-pick `max_concurrent`/`max_total_rss_mb` — call `resource_budget_from_percent(cpu_percent, ram_percent)` first (e.g. 80/80) to convert a "stay under X%" budget into concrete limits from the real detected machine, then pass those into `run_variants`.

## Notebook Hygiene

Start from `templates/notebook-skeleton.py`. Before push:

- One function per stage (load, feature-engineer, train/validate, predict, write-submission) — no monolithic cell of everything.
- Delete dead code, unused imports, and commented-out attempts; a notebook is read later, not just run once.
- Fit any encoder/scaler/imputer inside the CV loop, never on train+test combined, to avoid leakage.
- Fix every random seed (numpy, framework, split) so a rerun reproduces the same CV score.
- Print fold-by-fold CV scores and post-transform shapes — this is the only evidence Reviewer/Summarizer get without rerunning the notebook.
- Keep a summary docstring/cell at the top: `experiment_key`, hypothesis, `what_changed` — a human should understand intent in 10 seconds.
- Config constants (paths, target/id columns, seed, fold count) at the top, not scattered magic values through the body.

## Output Contract

Return:

- notebook path or Drive/Kaggle reference;
- source hash;
- smoke-test result;
- expected output files;
- any deviation from the approved plan.
