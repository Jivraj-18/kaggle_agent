---
name: kaggle-api-capabilities
description: Verified facts about how the real Kaggle CLI/API behaves — kernel CPU/RAM/disk limits, stdout quirks (pagination banners, enum-prefixed statuses, silent kernel-slug rewrites), and a critical security note about kernel environment variables. Use before assuming Kaggle resource limits or API response shapes, before writing code that parses Kaggle CLI output, or before printing/logging a Kaggle kernel's environment variables.
---

# Kaggle API Capabilities

Everything here was verified by actually running the Kaggle CLI/a real kernel, not read from docs — Kaggle's docs don't cover several of these. Re-verify anything time-sensitive (resource limits, docker image) if it's been a while; Kaggle updates its platform.

## Kernel resource limits (verified 2026-07-08, `gcr.io/kaggle-images/python`, CPU-only kernel)

- **CPU**: 4 cores (`os.cpu_count()`, `/proc/cpuinfo` agree).
- **RAM**: ~32.9GB total, ~31.9GB available.
- **Disk**: `/kaggle/working` and `/kaggle/input` share a 20.96GB volume (~20.94GB free) — this is the real output/working-file quota, not the container's root filesystem (which is much larger but isn't yours to fill).
- **ulimits**: unlimited (`RLIMIT_CPU`, `RLIMIT_AS` both `(-1, -1)`) — the real constraint is the container/VM allocation above, not a unix ulimit you can query generically.
- Re-verify with `scripts/probe_kernel_resources.py` — push it as a kernel and read the log.

## Security: never dump Kaggle kernel env vars wholesale

Every Kaggle kernel's environment includes real, live secrets injected by the platform (`KAGGLE_DATA_PROXY_TOKEN`, `KAGGLE_USER_SECRETS_TOKEN`, and similar). A naive `for k, v in os.environ.items(): if "KAGGLE" in k: print(k, v)` — written for exactly this kind of diagnostic — will print real tokens into your kernel log, which then gets downloaded and can end up in your own local files/shell history/context. Print variable **names**, never values, unless the name is on an explicit known-safe allowlist. `scripts/probe_kernel_resources.py` does this correctly — copy that pattern, don't write your own from scratch.

## Kaggle CLI/API stdout quirks

Use `scripts/kaggle_stdout_parsers.py` rather than re-deriving these:

- **Pagination banner breaks naive `json.loads`**: `competitions leaderboard --show --format json` (and similarly-paginated commands) print `Next Page Token = ...` on stdout *before* the JSON payload whenever more results exist than fit one page — which is effectively always for a real leaderboard. `json.loads` on the raw stdout throws. Use `parse_json_output`, which finds the first `[`/`{` and parses from there.
- **Submission/run status strings are enum-prefixed**: real API responses return `"SubmissionStatus.COMPLETE"`, not `"COMPLETE"`; kernel status is `"KernelWorkerStatus.COMPLETE"`, not `"COMPLETE"`. Naive string equality checks against bare status words silently fail. Use `normalize_status`.
- **A pushed kernel's real slug can silently differ from `kernel-metadata.json`'s `id`**: if `id`'s slug doesn't match Kaggle's clean-URL-slugification of `title`, Kaggle resolves to a *different* real slug, only warning about it in stdout ("Your kernel title does not resolve to the specified id...") while still exiting 0. Every later status/output call using the specified slug then fails with a real, confusing "permission denied" — not an auth problem, a wrong-slug problem. Parse the real slug from the `kaggle.com/code/<owner>/<slug>` URL Kaggle always prints on success with `parse_pushed_kernel_slug`, rather than trusting the id you specified. (Simplest fix: make `id` and `title` slugify to the same string in the first place.)
- **`competitions list -s <slug>` misses private/InClass competitions.** It only searches the public competition index — returns "No competitions found" even for a competition you've joined and can `competitions files`/`download` against fine. Don't treat that as "not joined" or "doesn't exist." Use `competitions files -c <slug>` or `competitions leaderboard <slug> --show` to check a specific competition directly instead.
- **A private/InClass competition's rules/overview page is unreachable without an authenticated browser session.** It's a client-rendered SPA — a plain HTTP GET (curl, most fetch tools) returns an empty shell with no rules text, regardless of auth. Get metric/target/column facts from `metadata.csv` (if the competition provides one) and the actual `train.csv`/`sample_submission.csv` instead; escalate rules-specific questions (internet/external-data allowed) that only the rules text can answer to a human who can view the page in a real browser.
- **A kernel linked to a competition via `kernel-metadata.json`'s `competition_sources`** (i.e. pushed via the API, not created from the competition page's "New Notebook" button) **mounts data at `/kaggle/input/competitions/<slug>/`, not `/kaggle/input/<slug>/`.** The latter path is only correct for a kernel created through the website. Wrong path fails at runtime with `FileNotFoundError` and no push-time warning.
