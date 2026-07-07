# Building a Local Kaggle Competition Agent System

## AutoKaggle accurately explained

AutoKaggle is not just “a few agents writing a notebook.” The paper’s core idea is a **phase-based workflow** for Kaggle-style data science problems, coupled to a **specialized multi-agent system** and a **tool-backed iterative development loop**. The workflow is explicitly divided into six phases: **background understanding**, **preliminary EDA**, **data cleaning**, **in-depth EDA**, **feature engineering**, and **model building, validation, and prediction**. The paper positions those phases as a way to decouple reasoning, keep state manageable, and enable testing at each stage rather than letting errors silently propagate into later work. AutoKaggle was evaluated mainly on **tabular Kaggle competitions**, and the authors describe it as providing end-to-end processing solutions for tabular data rather than as a general hosted-notebook orchestration framework. citeturn7view0turn38view0turn36view0

Its agent set is also narrower and more structured than many people assume. AutoKaggle uses five named agents: **Reader**, **Planner**, **Developer**, **Reviewer**, and **Summarizer**. The Reader appears in the background-understanding phase, where it reads the competition overview and sample data and produces a structured `competition info.txt` style summary. The Planner turns the current phase plus prior reports into a concrete plan. The Developer writes code for the current state using the plan, prior context, and available tools. The Reviewer scores and critiques agent outputs. The Summarizer reorganizes answers, generated artifacts, and reviewer assessments into phase reports. This is a tightly-scoped division of labor; it is not a free-form “agent swarm.” citeturn7view0turn9view2turn9view3turn9view4

The **iterative debugging and testing loop** is one of the most important parts of the paper, and it is the part most people omit when they try to reproduce the idea. The Developer does not generate code once and move on. Instead, it runs generated code, captures runtime errors, attempts self-debugging, reruns, and then applies **unit tests for the phase**. The paper describes three primary tools in this loop: **code execution**, **code debugging**, and **unit testing**. The implementation allows up to **five debugging attempts** within a phase, includes a “regenerate from scratch” escape hatch after repeated similar failures, and treats “runs without exceptions” as insufficient unless phase-specific tests also pass. In their experiments, each phase could be retried up to **three times** before being marked as a definitive failure. citeturn9view0turn9view1turn13view2turn13view3

The **tool library** is not just a bag of helper functions. AutoKaggle stores tool descriptions in a memory layer implemented as a **vector database**, uses a configuration file that maps tools to problem-solving states, and lets agents retrieve tool documentation via similarity search before using them. The tool set is organized by state. For data cleaning it includes things like missing-value handling, duplicate removal, datatype conversion, datetime formatting, and outlier handling. For feature engineering it includes one-hot encoding, label/frequency/target encoding, correlation and variance-based feature selection, scaling, PCA, RFE, polynomial features, and feature combinations. For modeling/validation/prediction it includes a train/validate/select-best-model tool. The authors emphasize that this library improves stability and completion rate more than it raises the absolute performance ceiling. citeturn10view0turn10view5turn11view0turn10view0turn8view1

The **reporting system** is also richer than a casual summary. The paper explicitly claims “comprehensive reporting,” and the Summarizer is tasked with generating structured markdown reports per phase. Those reports include fixed questions such as which files were processed and generated, what feature changes occurred, what transformations were applied, and what conclusions matter for the next stage. The Summarizer is also described as selecting relevant images, designing questions, and organizing responses into a report. So reporting in AutoKaggle is not an afterthought; it is a persistent knowledge artifact that feeds later planning. citeturn38view0turn9view4turn12view3turn12view5

The paper includes **human-in-the-loop** at two concrete points. Before planning, a human can inject manually crafted rules via a handbook-like memory source that influences prompt construction. After the Planner produces a plan, a human can review and refine it, especially where logic appears inconsistent or hallucinated. That is much more specific than “optional oversight.” In other words, AutoKaggle bakes in governance at the planning layer, not just at the final submission layer. citeturn10view0turn10view1

The headline numbers in the paper matter, but so does their scope. Across eight Kaggle competitions, the paper reports around **0.85 valid submission rate** and **0.82 comprehensive score**, with GPT-4o-based AutoKaggle outperforming their AIDE baseline on valid-submission rate. But those experiments were done on a set of mostly tabular competitions and measure the framework’s ability to reach valid submissions and reasonable normalized performance, not its ability to run a cloud-hosted asynchronous notebook farm under real Kaggle operations constraints. citeturn14view0turn14view1turn14view2

Your idea overlaps with AutoKaggle in one important way: both are trying to produce an **iterative closed loop** where the system reads competition context, proposes work, runs experiments, inspects results, and plans the next experiment. The big difference is that AutoKaggle’s loop is primarily an **internal phase-completion loop**, while your design is primarily an **external asynchronous execution loop** centered on Kaggle notebooks, CLI/API operations, and completion triggers. You are adding a cloud-execution and orchestration problem that AutoKaggle does not really solve. Conversely, AutoKaggle includes things your outline does not yet mention: phase decomposition, unit tests per phase, a purpose-built ML tool library, structured reports, and explicit human control points. citeturn7view0turn10view0turn10view1

My bottom-line comparison is this: **AutoKaggle is a reasoning architecture; your idea is an execution architecture**. To build something robust, you need both.

## What you are probably missing before you start

The most important thing you are likely underestimating is that **the experiment loop is not the notebook loop**. A notebook run is only one state transition in a larger system that includes rule parsing, baseline selection, local smoke tests, artifact hashing, result extraction, CV-vs-LB analysis, quota management, and approval policy. Kaggle’s CLI can list competition files, download data, submit to competitions, inspect submission history and leaderboard state, and manage kernels by push/pull/output/status. That is enough to automate a lot, but it is not a substitute for a durable experiment-control plane. citeturn33view0turn34view1turn16view0

You are also missing a **formal state model for artifacts**. Kaggle notebook automation becomes fragile very quickly if you do not know, for every experiment, which notebook version produced which output files, which submission candidate came from which kernel version, which prompts generated the notebook, and whether the competition rules snapshot changed between runs. Kaggle’s own interfaces are version-aware for kernels and code-competition submissions, which is a clue that your local system should be version-aware too. `kaggle kernels pull` can target a specific notebook version, and code-competition submissions can reference a specific notebook via `-k` and `-v`. citeturn33view0turn34view1

A second missing piece is **deterministic experiment accounting**. The CLI docs tell you that `kaggle kernels output` retrieves output from the **latest run** of a kernel, and Kaggle’s notebook guidance notes that the same notebook can have **multiple concurrent batch sessions**. Those two facts mean that a single long-lived notebook slug used for many concurrent experiments can create ambiguity around “which run produced these artifacts?” Unless you serialize runs strictly, you should assume you need either **one notebook slug per active experiment branch** or an internal policy that never allows more than one in-flight execution per slug. citeturn34view1turn18search0

A third omission is **competition compliance as a first-class subsystem**. Kaggle’s docs state that code competitions require submissions from inside a Kaggle Notebook, and competition documentation repeatedly warns that external data is allowed only when the competition rules say so. The CLI tutorial also says you must join the competition and accept its rules on the website before download or submit operations work. That means “read the rules page” is not optional context gathering; it is a required gating step in your state machine. citeturn17search1turn18search3turn35search0

A fourth omission is **cost and quota control**. Kaggle notebooks are a scarce execution substrate with time limits, concurrency limits, accelerator restrictions, and competition-specific hardware restrictions. If you let an LLM continuously spawn “one more experiment,” it will burn through notebook sessions, submission opportunities, and model tokens long before it converges on a high-quality solution. AutoKaggle partially solved this with phase gating, debugging caps, and human plan review. Your repo needs the same discipline, but applied to cloud execution and submissions. citeturn17search0turn18search0turn13view2

The fifth missing piece is **knowledge accumulation**. AutoKaggle writes structured reports after phases so future phases inherit distilled conclusions. Your design should do the same for runs. Otherwise the agent will keep rediscovering the same ideas, rerunning equivalent notebooks, and oscillating between small prompt variations. The right mental model is not “agent + notebook,” but **agent + memory + ledger + state machine + execution substrate**. citeturn9view4turn12view5turn38view0

## Proposed repository and system architecture

### What should run locally and what should run on Kaggle

Run **orchestration, planning, bookkeeping, compliance checks, report generation, local smoke tests, and lightweight data inspection** locally. Run **competition-constrained training and official code-competition submission notebooks** on Kaggle. Kaggle Notebooks are explicitly the hosted compute environment for code execution and, in code competitions, the required submission path. A local control plane is therefore not competing with Kaggle; it is supervising Kaggle. citeturn5search2turn17search1turn33view0

Locally, I would keep these responsibilities: competition ingestion, rules-page snapshotting, notebook template rendering, prompt/model execution, SQLite or Postgres state, output parsing, submission approval, and a tiny runner that can do **dry-run validation on a sampled subset** before you push anything to Kaggle. Kaggle should only see artifacts that already passed basic schema checks, import checks, and submission-format checks. This mirrors AutoKaggle’s philosophy that logical validation should happen before the next phase, not after the whole workflow collapses. citeturn9view1turn38view2

On Kaggle, keep the notebook as thin and reproducible as possible: load competition inputs, run the experiment, emit a strict artifact bundle, and optionally emit a submission candidate. Avoid making the notebook itself responsible for planning, memory, or orchestration. Notebooks should be **execution workers**, not the brain.

### Triggering and orchestration choice

Do **not** make email your primary trigger. Kaggle appears to support notebook-related notifications and user-facing email/site notifications, but that path is a consumer notification feature, not an automation contract. The CLI gives you things that are much more deterministic for automation: `kaggle kernels status`, `kaggle kernels output`, `kaggle kernels files`, and `kaggle competitions submissions`. Use those as your source of truth. Email can still be useful as a human alert channel. citeturn24search1turn24search15turn34view1turn33view0

For **v0**, use a **single local supervisor process plus SQLite** and poll Kaggle on an adaptive interval. A cron job is fine if you want simplicity, but a long-running local worker is better because it can maintain in-memory leases, backoff timers, and prompt caches. GitHub Actions is useful for repo hygiene, packaging, tests, and maybe nightly replays, but it is awkward as the main experiment loop because Kaggle notebook runs can be long, asynchronous, and stateful. Use Actions as CI, not as your brainstem.

For **v1**, move to a **queue-backed worker model**: one planner worker, one execution monitor worker, one artifact-ingest worker, and one reviewer/submission worker. Use Postgres for durable state and Redis or NATS for queues/signals. This is the point where message buses start paying for themselves. Before that, they are mostly ceremony.

### Core components

Your repo should have a small set of hard-edged components:

```text
agents/
  scout.py
  reader.py
  planner.py
  developer.py
  reviewer.py
  triage.py
  leakage_auditor.py
  lb_analyst.py
  report_writer.py

orchestration/
  supervisor.py
  state_machine.py
  scheduler.py
  event_bus.py
  approvals.py

kaggle_client/
  cli.py
  notebooks.py
  competitions.py
  outputs.py
  submissions.py
  auth.py

competitions/
  <competition_slug>/
    overview.md
    rules_snapshot.md
    files_manifest.json
    sample_submission.csv
    schemas/
    configs/

experiments/
  <competition_slug>/
    exp_0001/
      manifest.json
      plan.md
      notebook/
      prompts/
      outputs/
      metrics.json
      review.md

notebooks/
  templates/
    train_submit.ipynb.j2
    train_only.ipynb.j2
    infer_only.ipynb.j2

prompts/
  scout.md
  reader.md
  planner.md
  developer.md
  reviewer.md
  triage.md
  report_writer.md

state/
  app.db
  event_log.jsonl
  leases/
  caches/

reports/
  competition_briefs/
  experiment_reports/
  run_summaries/

configs/
  models.yaml
  routing.yaml
  budgets.yaml
  kaggle.yaml
  competitions.yaml

tests/
  test_state_machine.py
  test_submission_schema.py
  test_notebook_rendering.py
  test_output_parsing.py
```

This separation is important because Kaggle itself already gives you competition files, notebook versions, outputs, and submission history. Your repo should add the things Kaggle does **not** give you: planning state, experiment lineage, approvals, prompt/version tracking, and cross-run analysis. citeturn33view0turn34view1turn16view0

### What must be persisted after every run

Persist at least these artifacts after each run: notebook source, rendered metadata, prompt pack, planner output, local smoke-test result, Kaggle slug/version, status transitions, output file manifest, parsed metrics, generated submission file hash, competition submission ID and score, notebook accelerator settings, package/environment snapshot, and a reviewer summary.

For each Kaggle notebook version, I would track: slug, numeric id if available, notebook version, title, code hash, `machine_shape`, `enable_gpu`, `enable_internet`, `dataset_sources`, `competition_sources`, `kernel_sources`, `model_sources`, timeout, output manifest, runtime status, and any linked competition submission. Those are either explicit kernel metadata fields or direct consequences of CLI submission/version semantics. citeturn16view0turn34view1turn33view0

### Proposed v0 and v1

**v0** should be deliberately boring: one competition, one supervisor process, SQLite, notebook templates, three to five agents, manual submission approval, and polling-based completion detection. Your target is not “autonomous Kaggle”; your target is “reliable generation of the second experiment after the first one fails.”

**v1** can move closer to AutoKaggle: phase-specific subplans, state-specific test suites, vector-retrieved playbooks, richer agent decomposition, queue workers, experiment branching, and a proper report layer. The stronger AutoKaggle idea you should copy is the **phase/test/report discipline**, not necessarily the exact agent names. citeturn7view0turn10view0turn12view0

## Agent system design

### Which agents should exist

I would **not** copy AutoKaggle one-for-one as your operational architecture, even though I would absolutely copy parts of its reasoning architecture. AutoKaggle’s Reader/Planner/Developer/Reviewer/Summarizer set is a good cognitive skeleton, but your system needs additional agents or modules because you are adding asynchronous cloud execution, quota management, and rules enforcement. citeturn7view0turn9view2turn9view3turn9view4

For **v0**, I recommend this lean set:

1. **Competition Reader**: parse overview, rules, metric, sample submission, files, and constraints.
2. **Experiment Planner**: propose the next experiment from the ledger, not from raw logs alone.
3. **Notebook Developer**: render or update notebook code from a template plus plan.
4. **Reviewer/Critic**: check plan quality, code risks, and shallow-repetition risk.
5. **Execution Triage**: classify failure modes from notebook status, outputs, and submission history.
6. **Report Writer**: write short experiment reports and update competition memory.

For **v1**, add the role-specialists you mentioned, but only after the core loop is stable: **Competition Scout, Metric Specialist, Baseline Agent, Leakage Auditor, Leaderboard Analyst, Cost/Quota Manager, Feature Engineer, Model Search Agent, and Submission Gatekeeper**. My strong recommendation is to implement several of those initially as **skills inside the Planner/Reviewer**, not as full independent agents. Too many agents early will create expensive coordination noise rather than better science.

### Which AutoKaggle ideas are worth copying directly

Copy these parts almost unchanged:

- **Phase decomposition**.
- **State-specific validation tests**.
- **Structured reports after every step**.
- **Explicit reviewer critique before execution**.
- **Human approval at planning boundaries**.
- **Tool-backed, not free-form, code generation**. citeturn9view1turn12view0turn9view4turn10view1

Do **not** copy these too literally:

- a paper-era assumption that the main problem is local code synthesis rather than hosted execution control;
- a tabular-first tool library as though it generalizes automatically to NLP, CV, time series, or multimodal work;
- a single “Developer” agent that owns everything from code synthesis to iterative fixes to experiment branching.

### Strongest model versus cheaper model routing

Use the **strongest model** for work where mistakes compound downstream: competition understanding, rules interpretation, fold-scheme design, metric reasoning, experiment planning, hard debugging, and final review. Use **cheaper models** for repetitive parsing and bookkeeping: status summarization, file-manifest extraction, report compression, output classification, and “did this experiment materially differ from the previous one?” checks.

A practical routing policy is:

- **Frontier model**: Reader, Planner, hard Debugger, Reviewer, Leakage Auditor.
- **Mid-tier model**: Notebook Developer for first-pass edits, Triage agent, Baseline agent, LB Analyst.
- **Cheap model**: report condensation, JSON extraction, artifact parsing, state updates, retry messages.

This is exactly the place where OpenAI’s GPT-5.5/GPT-5.4 mini, Anthropic’s Opus 4.8/Sonnet 5, and Google’s Gemini 3.1 Pro / 3.5 Flash pairs are useful: each vendor now has an obvious “big brain + fast loop” combination. OpenAI explicitly recommends GPT-5.5 for complex reasoning/coding and GPT-5.4 mini for lower-latency, lower-cost workloads; Anthropic recommends Opus 4.8 for complex agentic coding and Sonnet 5 as the speed/intelligence balance; Google describes Gemini 3.1 Pro Preview as optimized for software-engineering and agentic workflows, while Gemini 3.5 Flash is targeted at rapid agentic coding loops. citeturn40search8turn39view0turn26view0turn26view2turn29view1turn29view0

### Where human approval is required

Require human approval at these checkpoints:

- after the system first parses competition rules;
- before enabling external data, internet, or pretrained assets in ambiguous competitions;
- before the first official submission in any competition;
- when CV and public LB disagree beyond a threshold;
- when the system proposes a leak-prone feature or a rules workaround;
- when the quota manager says you are near notebook or submission limits;
- when repeated no-improvement suggests overfitting to public LB.

That is stronger than the paper’s HIL points, but the added caution is justified because your loop is actually executing on Kaggle infrastructure and affecting real competition standing.

## ML workflow design

### How to prevent shallow one-notebook behavior

The best way to stop the system from degenerating into “generate notebook, run once, tweak randomly, repeat” is to force every run to belong to a **named hypothesis**. Every experiment should answer a question like: *Does GroupKFold reduce leakage relative to StratifiedKFold?* or *Does CatBoost outperform LightGBM on categorical treatment while preserving CV stability?* If the planner cannot state the hypothesis, required artifact, success metric, and stop condition, the experiment should not be enqueued.

I would make “baseline first” a hard rule in the state machine. The planner must first produce an **evaluable baseline family**, then a **gap analysis**, then a ranked shortlist of next hypotheses. AutoKaggle’s phase design helps here: if you import that discipline, your loop stops being “notebook generation” and becomes “stateful progress through understanding, validation, and controlled branching.” citeturn7view0turn12view0

### How to manage multiple hypotheses and experiments

Use an **experiment tree**, not a flat list. Each node should store: parent experiment, hypothesis, changed factors, expected effect, actual CV delta, actual public-LB delta, runtime cost, and verdict. Then restrict branching. I would allow:

- one active **baseline branch**;
- one active **feature branch**;
- one active **model branch**;
- one active **ensemble branch**.

Everything else waits in backlog. This keeps the search space legible.

The planner should also enforce a **minimum-difference policy**: if the proposed experiment only changes wording, logging, random seed without reason, or one parameter with no theoretical justification, the reviewer blocks it as repetitive.

### CV versus public leaderboard analysis

Your ledger should explicitly track both **OOF/CV metrics** and **public leaderboard results**. The system should compute:

- CV mean, std, and fold count;
- fold strategy class;
- submission file hash;
- public LB score;
- `lb_gap = public_lb - expected_oof_projection`;
- experimental rank correlation between OOF and public LB across recent runs.

This is how you detect when the system is optimizing public LB noise rather than model quality. If the rank order of experiments on CV stops matching public LB, that is not automatically a sign to trust the leaderboard more; it is usually a sign to inspect split design, leakage, or target-proxy features.

### Leakage, metric misuse, and invalid submissions

Create explicit checks for:

- target leakage through encoders or aggregations fit on train+validation together;
- train/test contamination via duplicate identifiers or row keys;
- wrong fold choice for grouped, temporal, or hierarchical data;
- metric mismatch, such as optimizing RMSE when the competition scores RMSLE or MAP@K;
- invalid submission schemas, row counts, column names, label ranges, or index mismatches.

AutoKaggle’s appendix is useful here because it concretely enumerates unit tests for cleaned data, processed data, and submission files: existence checks, duplicate checks, row-count checks, column-name checks, feature parity checks, and submission validity checks. You should build the Kaggle-execution analogue of those tests locally and again after output pull. citeturn38view2turn10view4

### Different competition families need different playbooks

For **tabular**, always start with dummy baseline, linear/logistic baseline, then LightGBM/CatBoost/XGBoost. For heavy categorical data, CatBoost frequently deserves early priority. For feature-heavy but small-to-medium data, tree methods with careful categorical treatment and leak-safe CV should dominate your first cycle.

For **NLP**, start with TF-IDF + linear model before transformer fine-tuning. The agent should first learn whether lexical baselines are strong, whether sequence length is short enough for efficient encoders, and whether the problem is single-label, multilabel, ranking, or retrieval-like.

For **CV**, first validate the image pipeline, labels, resize strategy, and augmentations with a tiny backbone or a frozen encoder. Then move toward stronger pretrained models. Avoid expensive heavy-training branches until the pipeline is proven end to end.

For **time series**, baseline with naive, seasonal naive, lag-feature tabular models, and only then move to deep sequence models. The system must choose split logic based on time, not convenience.

For **multimodal**, start with single-modality baselines and late fusion before deep joint modeling. Most agent systems waste too much time jumping directly to the “most advanced” multimodal stack.

### Baselines and scheduling

A sensible schedule is:

- **Always first**: schema checks, metric parser, dummy baseline, simplest strong baseline.
- **Then**: one model-strengthening branch and one feature-engineering branch.
- **Later**: feature selection, hyperparameter search, and error analysis.
- **Only after stable gains**: ensembling, pseudo-labeling, stacking.
- **Only when justified**: external data, pretrained external assets, domain-specific architectures.

Pseudo-labeling, stacking, and broad HPO are high-variance, quota-hungry moves. They are not early-loop defaults. They should be unlocked only after the system has established a reliable baseline and a trustworthy CV protocol.

## Kaggle-specific constraints and rule enforcement

### What Kaggle CLI and APIs can actually automate

Kaggle’s current official CLI supports competition listing, files, download, submit, submissions, leaderboard, and competition discussion topics. On the notebook side it supports listing kernels, initializing metadata, pushing notebooks/scripts, pulling code and metadata, fetching outputs, listing output files, checking latest-run status, and deleting kernels. For code competitions, the CLI can submit a file associated with a specific notebook and version via `-k` and `-v`. That means your basic automation loop is feasible without scraping every action. citeturn33view0turn34view1turn15search3

Kaggle also has two adjacent official interfaces worth knowing about. First, `kagglehub` provides Python access to Kaggle resources including **notebook outputs**, which can simplify post-run artifact pulls from Python. Second, Kaggle now documents an official remote **MCP server** at `kaggle.com/mcp`, which is interesting for future agent integration, though I would not make it a dependency for v0. citeturn32view0turn18search9

### Practical notebook constraints

Kaggle’s notebooks documentation currently says notebook editing sessions have **12 hours execution time for CPU and GPU sessions** and **9 hours for TPU sessions**. Kaggle’s efficient-GPU guidance also notes a **60-minute idle timeout** for interactive sessions. Competition docs further note that compute limits are visible within the editor and that code competitions can impose their own special constraints, including hardware, internet, or template restrictions. citeturn17search0turn17search3turn18search3

The kernels CLI supports accelerator selection and lists accelerators such as P100, T4, A100, L4, H100, and several TPU variants, while explicitly warning that some are only available in specific competitions or to admins. That tells you your scheduler needs an accelerator-availability layer rather than hardcoded assumptions. citeturn34view1

The official docs are also a reminder that **rules vary by competition**. Kaggle’s competition docs say external data is only allowed if the competition rules allow it, and code competitions may require template-specific notebook submissions. Some competition rules pages also require disclosure of external data or pretrained models. Your agent must therefore snapshot and parse each competition’s rules page before it decides anything about inputs, internet use, model assets, or submission style. citeturn23search0turn23search19turn33view0

### Is email notification fragile

Yes. It may exist, but it is fragile for orchestration. Kaggle has user-facing notebook notifications and profile-level notification settings, but those are not the same thing as an automation-grade event API. If a run finishes and the email is delayed, filtered, lost, or its subject/template changes, your loop stalls. The better method is: poll `kaggle kernels status`, then pull outputs, then poll `kaggle competitions submissions` if a submission candidate exists. Use email for **humans**, not for **state transitions**. citeturn24search1turn24search15turn34view1turn33view0

### Credentials and secure handling

Kaggle’s official docs now support OAuth, an `access_token` file, environment-variable token flow, and the legacy `kaggle.json` file. For a local agent repo, I would prefer **environment variables or the newer token/access-token path** over checking `kaggle.json` into any automation path. In GitHub Actions or any CI helper, store credentials as secrets and only materialize them at runtime. If you use `kagglehub`, it can reuse existing `kaggle` CLI configuration and also supports environment-variable token auth. citeturn19view0turn32view0

## Evaluation and model selection

### How to benchmark the system itself

Do not evaluate this system only by “final Kaggle score.” Track at least these metrics:

- valid notebook completion rate;
- valid submission generation rate;
- official submission acceptance rate;
- median time from plan to Kaggle completion;
- median time from Kaggle completion to next plan;
- average token cost per experiment;
- experiments per valid submission;
- public-LB improvement per dollar and per notebook-hour;
- percentage of experiments that introduced a genuinely new hypothesis;
- number of runs blocked by compliance or sanity gates;
- rate of repeated-no-improvement loops.

That is closer to how AutoKaggle evaluated completion and comprehensive score, but adapted to your asynchronous hosted setup. citeturn14view0turn14view1

To compare LLMs fairly, freeze the following: notebook template, tool access, competition set, budget, approval policy, maximum runs, maximum submissions, and stopping criteria. If you let different models use different numbers of experiments, longer contexts, or looser constraints, you will not be comparing models; you will be comparing whole systems.

### How to build a useful benchmark set

Do not build your benchmark around only easy tabular competitions. AutoKaggle’s own evaluation used eight mostly tabular tasks, which is useful for understanding the paper’s scope but should not become your design ceiling. A serious benchmark for your repo should cover at least these buckets:

- easy tabular classification;
- medium tabular regression;
- grouped or leakage-prone tabular;
- NLP text classification or ranking;
- image classification or detection;
- time-series forecasting;
- one code competition;
- one multimodal or document-heavy competition.

That way you measure whether your architecture generalizes, not whether it can repeatedly replay the same tabular pattern the paper already studied. citeturn36view0turn36view2

### Model recommendations to test first

As of today, the practical first wave I would test is this:

**OpenAI**
- **GPT-5.5** for competition understanding, planning, reviewing, and hard debugging. OpenAI’s docs position it as the default starting point for complex reasoning and coding, with a 1M context window. citeturn40search8turn30view0
- **GPT-5.5 Pro** for the hardest repo-level redesigns or difficult debugging sessions where latency matters less than accuracy. It is slower and much more expensive, but explicitly intended to “think harder.” citeturn30view1
- **GPT-5.4 mini** for cheap repeated loop iterations, artifact parsing, and subagent-style support tasks. OpenAI describes it as their strongest mini model for coding, computer use, and subagents. citeturn39view0turn40search5
- **GPT-5.3-Codex** only if you are using a coding-agent harness and want a specialized coding model. OpenAI still documents it as optimized for agentic coding, but also says that for most Codex work you should start with GPT-5.5. citeturn40search1turn31search0turn31search7

**Anthropic**
- **Claude Opus 4.8** for complex agentic coding and enterprise-grade harder tasks. Anthropic explicitly recommends starting there for complex agentic coding. citeturn26view0turn3view2
- **Claude Sonnet 5** for the speed/intelligence workhorse. Anthropic describes it as the best combination of speed and intelligence, with major gains in coding and agentic tasks. citeturn26view2turn3view1
- **Claude Fable 5** if you want to include Anthropic’s highest-capability widely released model in a premium benchmark tier. I would not start there for v0 because cost and latency will obscure your architecture bugs. citeturn26view0
- **Claude Haiku 4.5** for low-cost summarization and repetitive parsing. citeturn26view1

**Google**
- **Gemini 3.1 Pro Preview** for long-context competition understanding, planning, and tool-reliant repo tasks. Google says it is optimized for software engineering behavior and agentic workflows requiring reliable multi-step execution. citeturn29view1
- **Gemini 3.5 Flash** for rapid experiment loops, subagent work, and faster coding iterations. Google positions it specifically for real-world rapid agentic loops involving complex coding cycles. citeturn29view0
- **Gemini 3.1 Flash-Lite** for cheap repeated iterations, extraction, summaries, and state updates. Google explicitly frames it as a low-latency, cost-effective model for high-volume agentic workflows. citeturn29view2
- **Gemini 2.5 Pro** as a stable comparative baseline, especially if you want a known strong reasoning model with long-context support rather than only the newest series. citeturn29view3

### My concrete first test matrix

For your use case, I would start with exactly six model slots:

- **Planner / Reader primary**: GPT-5.5, Claude Opus 4.8, Gemini 3.1 Pro Preview
- **Loop worker / cheap subagent**: GPT-5.4 mini, Claude Sonnet 5, Gemini 3.5 Flash

That matrix will tell you much more, much faster, than benchmarking ten models at once.

I would **not** test only frontier models. Include one clearly cheaper model per provider as a baseline, because your eventual steady-state system will spend most of its cycles on repetitive work, not on “hardest possible reasoning.” The tradeoff is simple: frontier models reduce strategic mistakes; cheaper models determine whether the whole system is economically sustainable.

## Implementation package

### A concrete state machine

Your proposed state machine is directionally right, but it is missing a few critical pre- and postconditions. I would extend it like this:

```text
competition_discovered
  -> rules_snapshot_created
  -> rules_accepted
  -> data_downloaded
  -> competition_profile_built
  -> baseline_planned
  -> local_smoke_test_passed
  -> notebook_generated
  -> notebook_render_validated
  -> notebook_pushed
  -> notebook_running
  -> notebook_completed
  -> outputs_pulled
  -> validation_analyzed
  -> submission_candidate_created
  -> submission_checked
  -> human_submit_approved
  -> submitted
  -> leaderboard_recorded
  -> next_experiment_planned
  -> notebook_generated
  -> ...

terminal states:
  stopped
  escalated
  archived

failure states:
  runtime_error
  invalid_submission
  quota_exhausted
  metric_mismatch
  suspected_leakage
  repeated_no_improvement
  rule_violation_risk
  human_review_required
```

The transitions should behave like this:

- `runtime_error` goes to **triage**, then either regenerate notebook or escalate.
- `invalid_submission` goes to **submission schema fixer** and blocks official submit.
- `metric_mismatch` sends control back to **Competition Reader + Planner**.
- `suspected_leakage` suspends all feature/model branches until reviewed.
- `repeated_no_improvement` triggers a branch-pruning review.
- `quota_exhausted` pauses the queue and waits for quota windows or manual intervention.
- `rule_violation_risk` is a hard stop until a human approves or rewrites the plan.

### A minimal working prototype

Your MVP should be intentionally narrow:

1. one competition;
2. one notebook template;
3. one SQLite database;
4. one local supervisor process;
5. four agents: Reader, Planner, Developer, Reviewer;
6. local smoke tests before every push;
7. polling on `kernels status`;
8. output pull on completion;
9. manual approval before submission.

That MVP is enough to prove the real architecture: **state + planning + artifact lineage + Kaggle execution + controlled iteration**. If it works, you can add specialized agents later.

### A seven-day roadmap

**Day one**  
Build the skeleton: repo layout, config files, SQLite schema, Kaggle auth handling, and thin CLI wrappers for competitions, kernels, outputs, and submissions. Confirm you can join a competition, download files, initialize kernel metadata, push a notebook, poll status, and pull outputs. citeturn19view0turn33view0turn34view1

**Day two**  
Implement the competition reader path: overview snapshot, rules snapshot, file manifest, sample submission parser, metric parser, and a canonical `competition_profile.json`.

**Day three**  
Implement notebook templating and local smoke tests: import test, data path test, submission schema test, and one toy baseline notebook that writes predictable outputs.

**Day four**  
Add the first planner/developer/reviewer loop. Force every experiment to have a hypothesis, success metric, and stop condition. Add a repetition blocker.

**Day five**  
Add execution monitoring and output ingestion. Parse notebook outputs into structured local artifacts. Store experiment lineage and notebook version mapping.

**Day six**  
Add manual approval and submission pipeline. Poll submission history, record public scores, and write a one-page run report.

**Day seven**  
Run a full loop on one safe competition, then write the first branch-pruning logic and one compliance gate for external-data/internet use.

### Suggested prompts for the core agents

#### Competition Scout

```text
You are the Competition Scout.
Goal: produce a compact competition brief for downstream agents.

Inputs:
- competition overview page text
- rules snapshot
- file manifest
- sample_submission preview
- discussion/topic titles if available

Output JSON:
{
  "task_type": "",
  "prediction_target": "",
  "metric": "",
  "submission_schema": {},
  "data_modalities": [],
  "critical_rules": [],
  "allowed_external_data": true/false/"unclear",
  "allowed_internet": true/false/"unclear",
  "submission_limits": "explicitly quote if present, else unknown",
  "major_risks": [],
  "recommended_first_baselines": []
}

Requirements:
- prefer rules over assumptions
- if a rule is ambiguous, mark it unclear
- do not invent details missing from rules or files
```

#### Competition Reader

```text
You are the Competition Reader.
Goal: translate raw competition materials into a machine-usable profile.

Produce:
- problem framing
- target column
- metric and optimization direction
- file-by-file purpose
- likely feature families
- likely leakage risks
- candidate validation schemes
- exact submission column requirements

Always include:
- a section called "things that would invalidate a submission"
- a section called "rules requiring human confirmation"
```

#### Planner

```text
You are the Experiment Planner.
Goal: propose the single best next experiment, not a brainstorm.

Given:
- competition profile
- prior experiment ledger
- current best CV and LB
- quota status
- reviewer notes

Return JSON:
{
  "hypothesis": "",
  "why_now": "",
  "notebook_mode": "train_submit|train_only|infer_only",
  "changes": [],
  "expected_gain": "",
  "risk_level": "low|medium|high",
  "requires_human_approval": true/false,
  "local_tests_required": [],
  "kaggle_resources": {"gpu": false, "internet": false, "accelerator": ""},
  "stop_condition": ""
}

Rules:
- propose only one primary experiment
- do not repeat an already tested idea unless prior evidence was inconclusive
- do not recommend ensembling, pseudo-labeling, or stacking unless the baseline family is already stable
```

#### Developer

```text
You are the Notebook Developer.
Goal: modify or generate a Kaggle notebook that implements exactly the approved plan.

Constraints:
- keep notebook deterministic
- keep outputs explicit and named
- write a manifest.json at the end of the run
- emit submission.csv only if instructed
- never use data sources or internet access not explicitly allowed
- prefer simple, readable code over framework-heavy abstractions

Required outputs:
- /kaggle/working/manifest.json
- /kaggle/working/metrics.json
- /kaggle/working/submission.csv if relevant
- /kaggle/working/run_report.md
```

#### Reviewer

```text
You are the Reviewer.
Goal: block weak or repetitive experiments before they consume Kaggle quota.

Check for:
- missing hypothesis
- metric mismatch
- likely leakage
- invalid CV design
- shallow parameter twiddling
- unnecessary runtime/cost
- rule ambiguity
- poor reproducibility

Return:
- approve / reject
- top 3 reasons
- minimum fixes required
```

#### Error Triage

```text
You are the Error Triage Agent.
Goal: classify failures into actionable buckets.

Possible labels:
- dependency_error
- file_path_error
- kaggle_mount_error
- runtime_timeout
- oom_or_resource_error
- invalid_submission_schema
- metric_parser_error
- data_leakage_risk
- cv_design_failure
- unknown

For every failure:
- state the most likely cause
- give the smallest safe next change
- say whether a human should review
```

#### Leaderboard Analyst

```text
You are the Leaderboard Analyst.
Goal: interpret whether leaderboard movement is real.

Inputs:
- current experiment
- prior experiments
- CV history
- LB history

Output:
- whether the latest score is consistent with CV
- whether this looks like public-LB noise
- whether the branch should continue, stop, or ensemble later
```

#### Report Writer

```text
You are the Report Writer.
Write a terse but durable run report.

Always include:
- experiment id
- hypothesis
- what changed from parent
- local smoke-test result
- Kaggle notebook slug/version
- output files generated
- CV result
- LB result if submitted
- reviewer verdict
- next best experiment candidates
```

### The top thirty things you are most likely missing

1. A **rules snapshot** step before any planning.
2. A **competition profile** artifact that normalizes overview, metric, files, and schema.
3. A **submission-format validator** that runs locally before Kaggle.
4. A **local smoke-test layer** before notebook push.
5. A **notebook-template system** instead of free-form notebook generation every time.
6. A **single source of truth** for experiment state.
7. A **run ledger** that links experiment id to notebook slug and notebook version.
8. A **plan reviewer** that can reject weak experiments.
9. A **repetition detector** to stop prompt churn masquerading as research.
10. A **quota manager** for notebook hours, accelerator usage, and submission budget.
11. A **human approval gate** before official submissions.
12. A **human approval gate** for any ambiguous rules interpretation.
13. A **failure taxonomy** instead of generic “notebook failed.”
14. A **CV protocol registry** that records fold logic and why it was chosen.
15. A **CV-vs-public-LB divergence monitor**.
16. A **suspected leakage state** that suspends risky branches.
17. A **metric parser** that records whether higher or lower is better.
18. A **resource policy** that decides CPU vs GPU vs TPU per experiment.
19. A **one-notebook-per-active-branch** policy or strict serialized-run policy.
20. A **manifest file contract** for every Kaggle notebook run.
21. A **rules-aware data-source allowlist** for datasets, models, and internet.
22. A **structured report** after every completed run.
23. A **branching strategy** so experiments form a tree, not a pile.
24. A **baseline-first policy** that blocks fancy methods too early.
25. A **report-driven memory layer** so the planner reads conclusions, not raw logs.
26. A **submission deduplication policy** to avoid spammy near-identical submits.
27. A **rollback path** when a notebook template update breaks the loop.
28. A **model-routing policy** so expensive models are used only where they matter.
29. A **benchmark harness** to compare providers under fixed budgets and prompts.
30. A **stop policy** for repeated no-improvement, rule risk, or quota exhaustion.

### Do not build yet

Do not build these in your first iteration:

- a full message bus;
- a multi-competition fleet manager;
- automatic email-driven parsing as the main trigger;
- autonomous final submission without approval;
- broad HPO orchestration;
- pseudo-labeling before you trust your baseline;
- stacking before you have at least three stable base families;
- vector-database memory for everything;
- a fancy web dashboard;
- multi-provider dynamic bidding logic;
- speculative parallel execution across many Kaggle notebooks;
- a complete Kaggle discussion-mining subsystem.

Those are attractive, but most of them will hide whether your core loop is actually correct.

### Final recommendation on provider and model to start with

If you want the shortest path to a credible v0, I would start with **OpenAI GPT-5.5 as the main planner/reviewer and GPT-5.4 mini as the cheap loop worker**. The reason is not that the others are weak; it is that OpenAI’s current model lineup is especially explicit about the big-model/small-model pairing for coding, subagents, and tool use, and the docs are unusually clear about cost/latency tradeoffs. If you want a strong second-provider comparison immediately, add **Claude Sonnet 5** or **Gemini 3.5 Flash** as the fast-loop alternative, and **Claude Opus 4.8** or **Gemini 3.1 Pro Preview** as the heavy-planning alternative. citeturn40search8turn40search5turn26view0turn26view2turn29view0turn29view1

### Final risk assessment

The technical risk is moderate: the primitives exist. Kaggle’s official CLI can handle the essentials you need, including competition download/submit/submission history and notebook push/pull/output/status. The operational risk is higher: notebooks are asynchronous, quotas are finite, and competition rules vary enough that careless automation can waste runs or violate constraints. The research risk is also high: a poorly designed agent loop will look “active” while mostly generating shallow experiment churn. The dominant failure mode is not inability to push a notebook. It is **building an impressive orchestration shell around a scientifically weak experiment process**. citeturn33view0turn34view1turn17search0turn23search0

If you build v0 around **statefulness, deterministic artifacts, phase-aware planning, strict validation, polling-based execution control, and human-gated submission**, you will have something materially stronger than a notebook autopusher and much closer in spirit to the real contribution of AutoKaggle.