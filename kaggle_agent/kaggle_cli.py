import os
import json
import re
import subprocess
from dataclasses import dataclass


STATUS_RE = re.compile(r'status "([^"]+)"')


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
    text = result.stdout.strip()
    if not text or text == "No competitions found":
        return [], result
    return json.loads(text), result
