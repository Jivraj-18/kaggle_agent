"""Parsers for real, verified quirks in Kaggle CLI/API stdout.

Standalone (no third-party deps) so this can be copied into any project.
Each quirk here was found by running the real Kaggle CLI, not guessed —
see SKILL.md for how each was verified.
"""

import json
import re
from typing import Any


def parse_json_output(stdout: str, default: Any) -> Any:
    """Parse JSON from Kaggle CLI stdout, skipping any plain-text preamble.

    Paginated `--format json` output (e.g. `competitions leaderboard --show`)
    prints a "Next Page Token = ..." banner line on stdout before the JSON
    payload when more results exist than fit in one page. Plain json.loads
    chokes on that; find the first `[` or `{` and parse from there instead.
    """
    text = stdout.strip()
    if not text:
        return default
    starts = [idx for idx in (text.find("["), text.find("{")) if idx != -1]
    if not starts:
        return default
    return json.loads(text[min(starts):])


def normalize_status(value: Any) -> str | None:
    """Strip a Python-enum-style prefix, e.g. "SubmissionStatus.COMPLETE" -> "COMPLETE"."""
    if not value:
        return value
    return str(value).rsplit(".", 1)[-1]


def parse_pushed_kernel_slug(stdout: str) -> str | None:
    """kernel-metadata.json's "id" isn't guaranteed to be the real slug: if it
    doesn't match Kaggle's clean-url-slugification of "title", Kaggle silently
    resolves to a different slug, only warning about it in stdout while still
    exiting 0. Parse the real slug from the kaggle.com/code/<owner>/<slug> URL
    Kaggle always prints on success, rather than trusting the input arg.
    """
    match = re.search(r"kaggle\.com/code/([\w.-]+/[\w.-]+)", stdout)
    return match.group(1) if match else None
