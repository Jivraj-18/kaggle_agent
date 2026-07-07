import os
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any


STATUS_RE = re.compile(r'status "([^"]+)"')


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


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def kaggle_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
    env.setdefault("UV_TOOL_DIR", "/tmp/uv-tools")
    return env


def run_kaggle(args: list[str]) -> CommandResult:
    cmd = ["uvx", "kaggle", *args]
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
        env=kaggle_env(),
    )
    return CommandResult(cmd, proc.returncode, proc.stdout, proc.stderr)


def kernel_status(kernel_slug: str) -> tuple[str, CommandResult]:
    result = run_kaggle(["kernels", "status", kernel_slug])
    output = result.stdout + result.stderr
    match = STATUS_RE.search(output)
    status = match.group(1) if match else "UNKNOWN"
    return status, result


def kernel_output(kernel_slug: str, output_dir: str) -> CommandResult:
    return run_kaggle(["kernels", "output", kernel_slug, "-p", output_dir])


def kernel_push(path: str) -> CommandResult:
    return run_kaggle(["kernels", "push", "-p", path])


def competition_submit(competition_slug: str, file_path: str, message: str) -> CommandResult:
    return run_kaggle(["competitions", "submit", "-c", competition_slug, "-f", file_path, "-m", message])


def competition_submissions(competition_slug: str) -> CommandResult:
    return run_kaggle(["competitions", "submissions", competition_slug, "--format", "json", "--page-size", "200"])


def competition_leaderboard(competition_slug: str, page_size: int = 200) -> CommandResult:
    return run_kaggle(
        ["competitions", "leaderboard", competition_slug, "--show", "--format", "json", "--page-size", str(page_size)]
    )


def list_competitions(group: str, page_size: int = 100, search: str | None = None) -> tuple[list[dict], CommandResult]:
    args = [
        "competitions",
        "list",
        "--group",
        group,
        "--format",
        "json",
        "--page-size",
        str(page_size),
    ]
    if search:
        args.extend(["--search", search])
    result = run_kaggle(args)
    if result.returncode != 0:
        return [], result
    return parse_json_output(result.stdout, default=[]), result
