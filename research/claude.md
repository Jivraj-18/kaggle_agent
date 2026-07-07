# Design Document: An Agent-Driven Local Repository for Automating Kaggle Competitions with Codex CLI and Claude Code

## TL;DR
- **Build a local orchestrator that treats Kaggle as remote compute, and poll `kaggle kernels status` instead of relying on email** — the email trigger is the single most fragile idea in the plan and should be replaced by a deterministic state machine that polls kernel status. Copy AutoKaggle's *phase decomposition* and *Reviewer/unit-test loop* conceptually, but do not copy its architecture literally: AutoKaggle runs code in a local Python interpreter with an in-memory multi-agent loop, whereas your execution lives on Kaggle notebooks behind an async CLI, which changes everything.
- **Test OpenAI Codex CLI first with GPT-5.5 as the default driver model, GPT-5.4-mini for cheap loop iterations, escalating to Claude Code (Sonnet 5 default, Opus 4.8 for hard reasoning) as the second arm of a controlled A/B.** Compare on cost-per-task and iterations-to-first-valid-submission, NOT raw token counts, because Anthropic's Opus 4.7+/Sonnet 5 tokenizer emits ~30% more tokens for identical text.
- **Keep a human in the loop on every submission.** Kaggle allows automated ML tooling but enforces one-account-per-person, daily submission caps (commonly 5/day), and per-competition external-data/internet rules. An unsupervised submission loop is the highest-probability way to get disqualified or banned. The top 30 gaps, a v0/v1 architecture, a 7-day roadmap, prompts, and a risk assessment follow.

## Key Findings

**1. AutoKaggle is a tabular-only, synchronous, single-machine framework — your problem is asynchronous and distributed.** The paper (arXiv:2410.20424, Li et al., 44 pages, last revised Nov 5 2024) decomposes a competition into **six phases**: (1) background understanding, (2) preliminary EDA, (3) data cleaning (DC), (4) in-depth EDA, (5) feature engineering (FE), (6) model building, validation and prediction (MBVP). Five agents — **Reader, Planner, Developer, Reviewer, Summarizer** — execute these phases. The Developer runs an **iterative debugging + unit-testing loop**: code executes in a Python interpreter; on failure the error goes to the Reviewer; on success it goes to a **Unit Test Tool** whose failures are logged as short-term memory; Reviewer and Planner interact adversarially, with a **maximum of 3 iterations per phase** and 5 trials per task. It ships a **machine-learning tools library** (validated functions for DC/FE/MBVP, e.g. `OneHotEncode`, `FrequencyEncode`, `CorrelationFeatureSelection`, `TrainAndValidationAndSelectTheBestModel`). Per the paper, "AutoKaggle achieves a validation submission rate of 0.85 and a comprehensive score of 0.82 in typical data science pipelines," evaluated across **8 Kaggle competitions**. Different models were assigned per agent (GPT-4o/o1-mini for the Planner; GPT-4o-mini for Reader/Reviewer/Summarizer). Crucially: it evaluates offline, runs locally, and only covers classification/regression on tabular data.

**2. The Kaggle CLI can fully automate the loop — but there is no `run` verb; you push to run.** The verified command surface is `kaggle kernels {list, init, push, pull, output, status}`, `kaggle competitions {list, files, download, submit, submissions, leaderboard}`, and `kaggle datasets {...}`. A `kaggle kernels push` both uploads and *runs* the kernel. `kaggle kernels status` returns running/complete/error; `kaggle kernels output` pulls generated files (including `submission.csv` and the log). The `kernel-metadata.json` controls `enable_gpu`, `enable_internet`, `dataset_sources`, `competition_sources`, `kernel_sources`, and `--accelerator` (e.g. `NvidiaTeslaP100`, `NvidiaTeslaT4`, `TpuV6E8`). This means: create, push, run, poll, pull, and inspect are all scriptable. There is no email dependency needed.

**3. Kaggle's real constraints as of 2026.** Notebooks time out at **12 hours for CPU/GPU sessions and 9 hours for TPU** (all notebooks also carry a hard execution timeout — commonly cited at 9–12h). Weekly GPU quota is ~30 hours: per Kaggle's official product-feedback post (#173129), the "'floating' quota for GPU hours ... means that depending on demand, we may be able to provide more than 30 hours," and Kaggle docs state "The quota resets weekly and is 30 hours or sometimes higher depending on demand and resources." Per Kaggle discussion (general/135810), the quota "resets weekly on Saturday morning (midnight UTC) and every user is provided the same quota, which can be more than 30 hours." TPU is ~20 hours. Concurrent sessions are limited (GPU concurrency capped low, e.g. ~2; CPU batch sessions capped around 5). Dataset limit historically ~20GB per private dataset. Submissions are commonly **5/day per team** (some competitions 2/day). Code competitions require submission **from inside a notebook**, often with **no internet** and external-data restrictions. Public vs private leaderboard split means public LB is a *sample*.

**4. Codex and Claude Code both support headless automation with per-run telemetry.** Codex exposes `codex exec` (non-interactive; `--json` emits JSONL with a `turn.completed` `usage` object of `input_tokens`/`cached_input_tokens`/`output_tokens`; reasoning tokens may be omitted from the stream depending on version, and are written to the session rollout file unless `--ephemeral`). Claude Code exposes `claude -p --output-format json` with a documented `total_cost_usd` and `usage` object — the cleaner per-run measurement. Both support `--output-schema` / structured output, subagents, and cron/CI scheduling.

**5. Current models (July 2026).** Codex CLI default is **GPT-5.5** (released April 23 2026), fallback **GPT-5.4**, cheap tier **GPT-5.4-mini**; GPT-5.2/5.3-codex deprecated in ChatGPT-auth Codex; legacy API Codex models sunset July 23 2026. Claude Code default is **Claude Sonnet 5** (released June 30 2026), flagship **Claude Opus 4.8** ($5/$25 per MTok), cheap tier **Claude Haiku 4.5** ($1/$5). Fable 5 sits above Opus but has export-control availability turbulence. Published (vendor-reported, harness-dependent) benchmarks: GPT-5.5 leads Terminal-Bench 2.0 (~82.7%) and token efficiency; Opus 4.8 leads SWE-bench Pro (~69.2% vs ~58.6%, a ~10.6-point gap) but uses ~2.9× more output tokens per task.

## Details

### AutoKaggle architecture (accurate) vs your Kaggle-CLI/email idea

| Dimension | AutoKaggle (paper) | Your proposed loop | Implication |
|---|---|---|---|
| Execution | Local Python interpreter, synchronous | Kaggle notebook, async (push→poll→pull) | You need a state machine + polling, not a call stack |
| Trigger | In-process function returns | Email on completion | Email is fragile; poll `kernels status` |
| Agents | Reader/Planner/Developer/Reviewer/Summarizer | TBD | Adopt roles; add Kaggle-specific agents |
| Feedback | Interpreter stderr + unit tests | Notebook logs + `submission.csv` + LB score | Two feedback signals (CV and public LB) |
| Scope | Tabular classification/regression | Tabular, NLP, CV, time-series, multimodal | You need modality-specific playbooks |
| Debug loop | ≤3 iterations/phase, code exec + unit tests | Bounded by GPU quota + submission caps | Iterations are *expensive* (quota-limited) |

**What to copy from AutoKaggle:** the phase decomposition; the Reviewer↔Planner adversarial loop; unit tests as gates (does `submission.csv` exist? are columns correct? row count matches sample? no NaNs? target present?); per-phase reporting; and the ML tools library (pre-validated snippets so the LLM writes less bug-prone code). **What NOT to copy:** the synchronous in-process control flow, the assumption of instant re-execution, and the tabular-only tool library.

**Why iterations are precious.** MLE-bench (OpenAI, Chan et al., arXiv:2410.07095) quantifies the compute cost of agentic ML: "o1-preview with AIDE used 127.5M input tokens and 15.0M output tokens on average for one seed of 75 competitions," and "A single run of our main experiment setup of 24 hours per competition attempt requires 24 hours × 75 competitions = 1800 GPU hours of compute." Your Kaggle quota is ~30 GPU-hours/week, so every wasted notebook run is a material fraction of your weekly budget — the orchestrator must minimize failed pushes.

**Why email is the wrong trigger.** Kaggle email notifications are best-effort, subject to spam filtering (Kaggle's own terms disclaim undeliverable emails), have minutes-scale latency, and give you no structured payload. Polling `kaggle kernels status` on a backoff schedule (e.g. every 60–120s) is deterministic, gives machine-readable state, and lets you enforce timeouts. **Recommendation: local persistent orchestrator process (or `systemd` service) driving a state machine, with a polling worker per active kernel.** Skip cron for the core loop (cron gives you no in-flight state); use cron only for a watchdog. Skip GitHub Actions for execution (6-hour job cap, secrets exposure) though it is fine for nightly reporting. A message bus (Redis/RQ, Celery) is over-engineering for v0 — a single SQLite-backed state table plus a polling loop suffices until you run many competitions in parallel.

### 1. Architecture

**Runs locally:** the orchestrator, state store, the coding agent (Codex/Claude Code), prompt templates, competition rule cache, experiment ledger, generated notebook source, report generator. **Runs on Kaggle:** all data download, training, inference, `submission.csv` generation. **Local machine never trains models** (per your constraint).

**Agent communication:** do not build a chat-style multi-agent message bus in v0. Use the filesystem + state DB as the blackboard: each agent invocation is a headless `codex exec`/`claude -p` call with a scoped prompt and a JSON output schema; outputs are written to `state/` and `experiments/<id>/`. This is debuggable, resumable, and cheap.

**State storage:** a single SQLite DB (`state/experiments.db`) with tables for competitions, experiments, kernel_versions, submissions, and leaderboard_snapshots. Persist after each run: kernel slug + version, `kernel-metadata.json`, notebook source hash, full log, CV score, public LB score, submission id, GPU-seconds consumed, wall-clock, agent token/cost telemetry, and the hypothesis being tested.

### 2. Agent design

Adopt AutoKaggle's five roles, then add Kaggle-specific ones. Recommended agent set with model tiering:

| Agent | Role | Model tier |
|---|---|---|
| **Competition Scout / Reader** | Parse competition page, data schema, metric, sample submission, rules | Strong (GPT-5.5 / Sonnet 5) once per competition |
| **Rules/Leakage Auditor** | Extract machine-readable rules (submission cap, internet, external data, AI-tool policy); flag leakage/train-test mismatch | Strong; human-reviewed |
| **Metric Specialist** | Implement the exact metric locally for CV; detect metric misuse | Strong |
| **Planner** | Decompose into experiment queue; prioritize hypotheses | Strong (reasoning) |
| **Baseline Agent** | Always ship a trivial + a strong baseline first | Cheap (GPT-5.4-mini / Haiku 4.5) |
| **Developer** | Generate/patch notebook code | Strong-to-mid |
| **Error Triage Agent** | Classify notebook failures from logs; propose fix | Mid; cheap for known errors |
| **Reviewer** | Unit-test gate + critique before push/submit | Mid |
| **Leaderboard Analyst** | Compare CV vs public LB; detect overfitting to public LB | Mid |
| **Cost/Quota Manager** | Track GPU-hours, submission budget; gate expensive runs | Deterministic code, not an LLM |
| **Summarizer/Report Writer** | Per-experiment + per-competition reports | Cheap |

**Human approval required at:** (a) accepting competition rules, (b) any submission, (c) any external-data or internet-enabled notebook, (d) escalations. The Cost/Quota Manager should be plain code, not a model call.

### 3. ML workflow

**Preventing shallow "one-notebook" behavior:** enforce a persistent *experiment queue* with explicit hypotheses; the Planner may not generate a notebook without stating the hypothesis, the expected CV delta, and the cost. Require a strong baseline before any fancy modeling. Track a CV↔LB scatter to detect public-LB overfitting (large positive CV gain with flat/negative LB movement ⇒ leakage or overfit).

**Always-first baselines:** tabular → mean/mode + a gradient-boosted tree (LightGBM/XGBoost/CatBoost) with honest k-fold CV; NLP → TF-IDF + linear, then a small transformer; CV → a pretrained backbone + linear head; time-series → last-value/seasonal-naive + a lag-feature GBM with time-based splits; multimodal → per-modality baselines then late fusion. **Leakage/validation checks as unit tests:** target present only in train; no train/test feature-distribution drift beyond threshold; time-ordered splits for temporal data; group-aware folds where IDs repeat; submission schema exactly matches sample; deterministic seed; row counts match.

**Scheduling of advanced techniques:** only after a stable baseline and a trustworthy CV↔LB relationship — order is feature selection → hyperparameter search → error analysis → ensembling/stacking → pseudo-labeling. Each is a queued experiment gated by the Cost/Quota Manager.

### 4. Kaggle-specific constraints (facts)

- **Session/timeout:** ~12h CPU/GPU, 9h TPU per session; long jobs must checkpoint to a Kaggle Dataset (kernel-chaining pattern) because there is no persistent disk.
- **Weekly quota:** GPU ~30h (explicitly "floating"/demand-based bonus possible), TPU ~20h, reset Saturday 00:00 UTC.
- **Concurrency:** low GPU concurrency (≈2); CPU batch sessions capped (≈5). Plan a queue.
- **Submissions:** commonly 5/day per team (2/day in some). Enforce in code.
- **Internet/external data:** code competitions often forbid internet; external data allowed only if the competition says so. `enable_internet=false` by default in metadata.
- **CLI reliability:** create/push/run/poll/pull/inspect are reliable; `kaggle kernels output` fetches logs + files. Track per-version metadata: slug, version number, source hash, GPU flag, accelerator, dataset/competition sources, status, runtime, output file list.
- **Credentials:** store `kaggle.json` at `~/.kaggle/kaggle.json` (chmod 600) or `KAGGLE_USERNAME`/`KAGGLE_KEY` env vars; never commit; keep out of the repo and out of any notebook the agent uploads.

### 5. Repository structure

```
kaggle-agent/
├── agents/            # prompt-driven agent wrappers (scout, planner, developer, reviewer, ...)
├── orchestration/     # state machine, polling workers, scheduler, retry/backoff
├── kaggle_client/     # thin wrapper over kaggle CLI/API: push, status, output, submit
├── competitions/      # per-competition: cached rules, metric.py, data schema, playbook
├── experiments/       # per-experiment: hypothesis.json, notebook.ipynb, logs, scores
├── notebooks/         # generated notebook templates + rendered versions
├── templates/         # kernel-metadata.json templates, notebook skeletons per modality
├── prompts/           # versioned prompt files per agent
├── state/             # experiments.db (SQLite), locks, run ledger
├── reports/           # per-experiment and per-competition markdown reports
├── configs/           # model tiering, budgets, quotas, competition config
└── tests/             # unit tests incl. submission-schema validators
```

### 6. State machine

States: `competition_discovered → rules_accepted(human) → data_downloaded → baseline_planned → notebook_generated → notebook_pushed → notebook_running → notebook_completed → outputs_pulled → validation_analyzed → submission_checked → submission_approved(human) → submitted → leaderboard_recorded → next_experiment_planned → (loop) → stopped/escalated`.

Failure states and transitions:
- `runtime_error` → Error Triage → patch → `notebook_generated` (retry, max 3, exponential backoff); after 3 → `human_review_required`.
- `invalid_submission` (schema/columns/rows) → Reviewer unit-test fix → regenerate; never counts against daily cap if caught locally *before* submit.
- `quota_exhausted` → pause competition until reset (Sat 00:00 UTC); Cost/Quota Manager schedules.
- `metric_mismatch` (local CV metric ≠ Kaggle metric) → Metric Specialist → block submission.
- `suspected_leakage` (CV≫LB) → Leakage Auditor → `human_review_required`.
- `repeated_no_improvement` (N experiments no LB gain) → escalate to human or switch strategy branch.
- `rule_violation_risk` (internet/external data/AI-policy) → hard stop → `human_review_required`.

Retry policy: transient CLI/network errors retried with backoff; logic errors escalate after bounded attempts. Every submission requires human approval regardless of state.

### 7. Evaluation and benchmarking

Track beyond Kaggle score: **cost per experiment ($), tokens per experiment, wall-clock latency, GPU-seconds, valid-submission rate, iterations-to-first-valid-submission, iterations-to-baseline-beat, leaderboard percentile, reliability (% runs without runtime error).** For the Codex vs Claude Code comparison: run the **same competitions, same GPU/submission budgets, same prompts and scaffolding**, and compare on **cost-per-task and iteration count**, NOT raw token counts (tokenizer differences make raw counts non-comparable). Build a benchmark set spanning modalities and difficulty; reference **MLE-bench** as prior art and as a balanced competition list. Per the MLE-bench paper, the best setup "OpenAI's o1-preview with AIDE scaffolding — achieves at least the level of a Kaggle bronze medal in 16.9% of competitions" at pass@1, "doubl[ing] from 16.9% using pass@1 to 34.1% using pass@8." Its 75 competitions are deliberately balanced by difficulty: "22 competitions Low in complexity (30%), 38 Medium (50%), and 15 High (20%)." Mirror that difficulty spread and modality spread (tabular/NLP/CV/time-series) so you do not overfit your system to easy tabular competitions.

### 8. Model / agent selection

**Test Codex first** (your primary subscription). Recommended mapping:
- Repository-level coding / notebook debugging: **GPT-5.5** (Codex), later compare **Opus 4.8** (Claude Code).
- Long-context competition understanding: GPT-5.5 (1M context) / Sonnet 5 or Opus 4.8 (1M context).
- ML experiment planning / reasoning: strongest available (GPT-5.5 / Opus 4.8).
- Cheap repeated loop iterations: **GPT-5.4-mini** / **Haiku 4.5**.
- Reviewing/critique: mid-tier.
- Summarization/reporting: cheap tier.

**Frontier-first, then add cheap baselines.** Start with frontier models to establish the *ceiling* of what the system can do; then substitute cheaper models on the high-frequency loop steps (triage, review, summarize) to measure the cost/quality tradeoff. Running only frontier models everywhere wastes budget on trivial steps; running only cheap models understates the system's potential.

**Fair-comparison mechanics.** Prefer running both tools via **API key / per-token billing** so `total_cost_usd`-style figures are real dollars (subscription usage is credit/window-based and its reported cost is not billed). Use `claude -p --output-format json` (documented `total_cost_usd` + `usage`) and `codex exec --json` (log the rollout file for reasoning tokens; avoid `--ephemeral`). Because Anthropic states its Opus 4.7+/Sonnet 5 tokenizer "produces approximately 30% more tokens for the same text," normalize on cost-per-resolved-task and iteration/turn count rather than raw token totals. The published Terminal-Bench gap is contaminated by different harnesses (Codex CLI vs Terminus-2), which is itself the reason to run your own controlled head-to-head.

### 9. Safety, compliance, Kaggle rules

Kaggle explicitly **permits automated ML tooling** but requires: **one unique account per person** (submitting from multiple accounts ⇒ disqualification), **no private code/data sharing outside teams**, daily submission caps, and per-competition external-data/internet restrictions. Some competitions have specific AI-tool-usage or reproducibility rules. The Rules/Leakage Auditor must parse each competition's rules into machine-readable flags and the Cost/Quota Manager must hard-enforce the submission cap. **Keep human-in-the-loop on submissions** to prevent automated spam submissions and rule violations. Never enable internet/external data unless the parsed rules explicitly allow it.

### 10. Required deliverables

**(a) Top 30 things the user is likely missing** — see Recommendations list.

**(b) v0 architecture (one local repo):** single Python orchestrator + SQLite state + `kaggle_client` wrapper + one Codex agent invoked headlessly per step + polling worker + human approval gate on submit. One competition at a time. Baselines + bounded debug loop + manual submit.

**(c) v1 architecture (closer to AutoKaggle):** full agent set with phase decomposition, Reviewer/unit-test gate, ML tools library, per-phase reports, experiment queue with hypothesis tracking, CV↔LB analytics, and the Codex-vs-Claude-Code A/B harness. Multiple competitions in parallel with a queue.

**(d) 7-day roadmap:** Day 1 — `kaggle_client` wrapper + auth + push/status/output/submit round-trip on Titanic. Day 2 — SQLite state + state machine skeleton + polling worker. Day 3 — notebook templating + `kernel-metadata.json` generation + submission-schema unit tests. Day 4 — Codex headless integration (scout + developer + reviewer) with JSON output. Day 5 — baseline agent + local CV + metric implementation + CV↔LB logging. Day 6 — error triage loop + quota/submission enforcement + human approval gate. Day 7 — reporting + run on 2–3 competitions across modalities; capture cost/iteration telemetry.

**(e) Minimal working prototype:** Titanic (or a current playground) → agent reads page/data/metric → generates a LightGBM notebook with 5-fold CV → pushes with `enable_gpu=false` → polls status → pulls `submission.csv` + log → validates schema → surfaces CV score and asks human to approve submission → records LB score.

**(f) Prompts per agent** — provided in Recommendations.

**(g) Recommendation:** start with **Codex CLI + GPT-5.5** as driver, **GPT-5.4-mini** for loop iterations, `codex exec --json` for telemetry, one competition, human-gated submit. Reason: it is your existing subscription, has strong long-context + token efficiency, and headless JSON telemetry is adequate for the loop. Add Claude Code (Sonnet 5 / Opus 4.8) as arm B once the harness is stable.

**(h) Do NOT build yet:** message bus/Celery; multi-competition parallelism; a custom web dashboard; auto-submission without human approval; a bespoke fine-tuned router model; email parsing; local GPU training; a full replica of AutoKaggle's tool library before you have a working single loop; ensembling/stacking/pseudo-labeling automation before a trustworthy CV.

**(i) Risk assessment:** highest risks are (1) account ban / disqualification from automated or multi-account submissions — mitigate with human-gated submits and one account; (2) burning GPU quota on buggy notebooks — mitigate with local dry-runs and CPU-first debugging; (3) public-LB overfitting — mitigate with CV↔LB analytics; (4) leakage / metric mismatch producing false progress — mitigate with the Auditor and Metric Specialist; (5) cost runaway from frontier-model loops — mitigate with budget caps and cheap-tier loop steps; (6) rule changes / CLI changes — mitigate by pinning CLI version and re-parsing rules per competition.

## Recommendations

**Staged next steps:**
1. **Days 1–2 (plumbing):** Build `kaggle_client` and prove a full push→poll→pull→submit round-trip on Titanic manually. Benchmark to change plan: if `kaggle kernels status`/`output` prove unreliable, add retries and treat the ledger as source of truth.
2. **Days 3–4 (agent loop):** Wire Codex headless with JSON output; implement submission-schema unit tests as the Reviewer gate. Threshold: do not proceed until the agent can generate a schema-valid submission unattended.
3. **Days 5–6 (ML quality + safety):** Add local CV + metric implementation + CV↔LB logging + quota/submission enforcement + human approval. Threshold: baseline must beat the trivial submission on honest CV before advanced techniques unlock.
4. **Day 7+ (measure + compare):** Run across 2–3 modalities; only then stand up the Claude Code arm. Switch models on loop steps if cheap-tier quality is within tolerance.

**Top 30 things you are likely missing:** (1) email triggers are unreliable — poll status; (2) there is no `kaggle kernels run` — push runs it; (3) 12h/9h session timeouts force checkpointing; (4) ~30h weekly GPU quota caps iterations; (5) low concurrent-session limits force a queue; (6) 5/day submission cap must be enforced in code; (7) public LB is a sample — overfitting risk; (8) one-account-per-person rule; (9) no-internet/no-external-data in code comps; (10) no persistent disk — use kernel-chaining via Datasets; (11) metric must be re-implemented locally for CV; (12) group/time-aware CV folds; (13) submission schema must match sample exactly; (14) tokenizer differences make raw token comparison invalid; (15) reasoning tokens may be hidden in Codex JSON; (16) `--ephemeral` drops the rollout log you need for telemetry; (17) human approval on submit is a compliance necessity; (18) GPU type is not selectable via metadata; (19) quota resets Saturday 00:00 UTC — schedule around it; (20) notebook environment packages are fixed — no arbitrary installs offline; (21) AutoKaggle is tabular-only — you need modality playbooks; (22) experiment state must be persisted for resumability; (23) a strong baseline must precede fancy modeling; (24) cost caps per experiment; (25) leakage detection as a first-class gate; (26) rules differ per competition and must be re-parsed; (27) dataset upload size limits (~20GB); (28) private vs public kernel visibility affects sharing rules; (29) MLE-bench is a ready-made balanced benchmark set (22 Low / 38 Medium / 15 High complexity); (30) don't optimize only for easy tabular comps.

**Prompt sketches per agent:**
- *Scout/Reader:* "You are given the competition overview, data schema, evaluation page, sample submission, and rules text. Output JSON: {problem_type, modality, metric_name, metric_direction, submission_columns, row_id_key, external_data_allowed, internet_allowed, submissions_per_day, notable_constraints}. Quote the rules verbatim for each flag."
- *Rules/Leakage Auditor:* "Given rules text and data schema, output machine-readable flags and list every clause that restricts data, internet, accounts, or AI tools. Flag any feature that could leak the target or any train/test distribution mismatch. Escalate to human if uncertain."
- *Metric Specialist:* "Implement the exact competition metric as `metric.py` with a test against the sample submission. Confirm direction (maximize/minimize)."
- *Planner:* "Given current best CV/LB and prior experiments, output an ordered experiment queue. Each item: {hypothesis, expected_cv_delta, estimated_gpu_minutes, estimated_cost}. Require a strong baseline before advanced techniques."
- *Baseline Agent:* "Generate a notebook with a trivial baseline and a LightGBM (or modality-appropriate) baseline using honest k-fold CV. Write `submission.csv` to /kaggle/working."
- *Developer:* "Given the current notebook and the next hypothesis, produce a minimal diff. Do not enable internet or external data unless flags allow. Keep runtime under session limits."
- *Error Triage:* "Given notebook logs, classify the failure (ValueError/KeyError/TypeError/OOM/timeout/FileNotFound), cite the line, and propose the minimal fix."
- *Reviewer:* "Run the submission-schema unit tests. Reject if columns/rows/NaN/target checks fail. Summarize risk before push/submit."
- *Leaderboard Analyst:* "Given CV and public LB history, flag public-LB overfitting and recommend whether to trust CV."
- *Summarizer/Report Writer:* "Produce a markdown report: hypothesis, what ran, CV, LB, cost, GPU-seconds, decision, next step."

## Caveats
- Kaggle limits fluctuate (the GPU quota is explicitly "floating" and demand-based); treat 30h/12h/5-per-day as current norms and re-verify per competition, since some are secondary-source or forum-sourced.
- Model/plan details for Codex and Claude Code are current to July 2026 and change frequently; several benchmark figures (SWE-bench Pro, Terminal-Bench, the ~30% tokenizer inflation, ~2.9× output tokens) are vendor-reported and harness-dependent and were not all confirmable against a single authoritative primary source — the published Terminal-Bench gap in particular is contaminated by different harnesses, which is itself an argument for running your own controlled comparison.
- Codex per-run reasoning-token exposure in `--json` is version-dependent; verify on your installed CLI version and avoid `--ephemeral` if you need the rollout telemetry.
- AutoKaggle figures (0.85 valid-submission rate / 0.82 comprehensive score) are on 8 tabular competitions only and do not generalize to NLP/CV/time-series/multimodal.
- Kaggle competition rules vary; nothing here overrides a specific competition's rules or Kaggle's Terms of Use. Confirm automated-tooling and submission policies per competition before running unattended.