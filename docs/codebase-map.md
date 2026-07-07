# Codebase Map

Use this map to decide where a coding agent should make changes.

## Runtime Graph

```mermaid
flowchart TD
    CLI[kaggle_agent/cli.py] --> State[kaggle_agent/state.py]
    CLI --> Kaggle[kaggle_agent/kaggle_cli.py]
    CLI --> Scout[kaggle_agent/scout.py]
    CLI --> Artifacts[kaggle_agent/artifacts.py]
    CLI --> Drive[kaggle_agent/drive_sync.py]
    Drive --> GWS[kaggle_agent/gws_cli.py]

    State --> JSON[(state/*.json)]
    Artifacts --> ArtifactState[(state/artifacts.json)]
    Artifacts --> ArtifactFiles[(artifacts/ ignored)]
    Kaggle --> KaggleRemote[Kaggle CLI / notebooks]
    GWS --> DriveRemote[Google Drive]
```

## Agent Graph

```mermaid
flowchart LR
    User[English user request] --> AGENTS[AGENTS.md]
    AGENTS --> Skills[skills/*.md]
    Skills --> Personas[agents/*.md]
    Personas --> CLI[kaggle_agent/cli.py]
    CLI --> State[(state/*.json)]
    State --> Personas
```

## State Graph

```mermaid
flowchart TD
    Competition[competitions.json] --> Profile[profiles.json]
    Competition --> Experiment[experiments.json]
    Experiment --> Notebook[notebooks.json]
    Experiment --> Run[runs.json]
    Run --> Artifact[artifacts.json]
    Experiment --> Submission[submissions.json]
    Run --> Submission
    Session[observability/sessions.jsonl] --> Metrics[observability/metrics.json]
    Experiment --> Metrics
    Run --> Metrics
    Submission --> Metrics
```

## Change Targets

- New CLI command: edit `kaggle_agent/cli.py`, add tests in `tests/test_cli.py`.
- New state file/default: edit `kaggle_agent/state.py`, update `docs/state-schemas.md`.
- Kaggle CLI behavior: edit `kaggle_agent/kaggle_cli.py`; keep wrappers thin.
- Google Drive behavior: edit `kaggle_agent/drive_sync.py` or `kaggle_agent/gws_cli.py`.
- Output/log/submission artifact behavior: edit `kaggle_agent/artifacts.py`.
- Competition scouting shape: edit `kaggle_agent/scout.py`.
- User-facing workflow prompt: edit `skills/<workflow>/SKILL.md`.
- Role/persona behavior: edit `agents/<role>.md`.
- Notebook/report skeleton: edit `templates/`.

## Design Constraint

Keep production code small. Prefer simple state records and explicit tests over framework code. Do not add a new abstraction unless it removes repeated behavior across at least two real commands.
