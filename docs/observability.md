# Observability (Langfuse)

Browse real prompts/responses from every Claude Code and Codex session on
this project, grouped by session, in a self-hosted web UI. Only run this
when you actually want to look — it's not meant to run continuously.

## Start it

```bash
cd observability/langfuse
cp .env.example .env   # then fill in real secrets, see comments in that file
docker compose up -d
```

Web UI: http://localhost:3000 (log in with the `LANGFUSE_INIT_USER_EMAIL`/
`LANGFUSE_INIT_USER_PASSWORD` you set in `.env`).

## Push session history into it

```bash
uv sync --extra observability
LANGFUSE_PUBLIC_KEY=<from .env> LANGFUSE_SECRET_KEY=<from .env> LANGFUSE_HOST=http://localhost:3000 \
  uv run python -m kaggle_agent.cli observability push-langfuse --json
```

Discovers every real Claude Code transcript under `~/.claude/projects/<this
project's slug>/` and every Codex session under `~/.codex/sessions/` whose
recorded `cwd` matches this project — not just sessions that got a manual
`sessions start`/`end` call, since that registration is known to drift (see
`docs/architecture.md#observability`). Idempotent: already-pushed
`session_id`s are tracked in `state/observability/langfuse_synced.json`, so
re-running only pushes what's new. Gemini isn't supported — no real Gemini
CLI session transcripts exist to develop the parser against yet
(`kaggle_agent/langfuse_sync.py`, `kaggle_agent/prompt_history.py`).

One trace per session, one generation per prompt/response exchange, grouped
by Langfuse "Sessions" and tagged with harness/model/skill/competition where
that metadata is known (from `state/observability/sessions.jsonl`).

## Sharing it

`cloudflared tunnel` + a DNS record, same as any other local web app. Do
**not** point a tunnel at an instance still using the throwaway defaults —
regenerate every `.env` secret first (see comments in `.env.example`).

## Stop it

```bash
cd observability/langfuse && docker compose down
```
