"""Run several CPU-only experiment variants concurrently within one Kaggle
session/push instead of one variant per push. See GitHub issue #1 and
agents/developer.md. Never use this for GPU work — a GPU run is real Kaggle
quota, not a cheap speculative branch, and stays one-at-a-time.
"""

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO


@dataclass(frozen=True)
class VariantSpec:
    name: str
    command: list[str]
    log_path: Path


@dataclass(frozen=True)
class VariantResult:
    name: str
    returncode: int
    log_path: Path


def read_rss_mb(pid: int) -> float:
    """Resident memory of a process in MB, via /proc (Linux — matches both
    Kaggle's kernel containers and typical dev machines). Returns 0.0 if
    unreadable (process already exited, permission denied, non-Linux)."""
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except (FileNotFoundError, ProcessLookupError, ValueError, PermissionError):
        pass
    return 0.0


def total_ram_mb() -> float:
    """Total system RAM in MB, via /proc/meminfo (Linux — matches Kaggle's
    kernel containers). Returns 0.0 if unreadable."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024
    except (FileNotFoundError, ValueError):
        pass
    return 0.0


def resource_budget_from_percent(
    cpu_percent: float,
    ram_percent: float,
    cpu_count: int | None = None,
    total_ram_mb_value: float | None = None,
) -> tuple[int, float]:
    """Convert "stay within X% of CPU/RAM" into concrete (max_concurrent,
    max_total_rss_mb) for run_variants. Detects the real machine's specs by
    default (os.cpu_count(), total_ram_mb()); cpu_count/total_ram_mb_value
    let tests (or a caller with better info, e.g. a known Kaggle kernel
    profile) inject known values instead. max_concurrent is always at least
    1, regardless of how low cpu_percent is or how few cores exist."""
    if not 0 < cpu_percent <= 100:
        raise ValueError("cpu_percent must be in (0, 100]")
    if not 0 < ram_percent <= 100:
        raise ValueError("ram_percent must be in (0, 100]")
    cores = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    ram_mb = total_ram_mb_value if total_ram_mb_value is not None else total_ram_mb()
    max_concurrent = max(1, int(cores * cpu_percent / 100))
    max_total_rss_mb = ram_mb * ram_percent / 100
    return max_concurrent, max_total_rss_mb


def run_variants(
    variants: list[VariantSpec],
    max_concurrent: int,
    max_total_rss_mb: float | None = None,
    poll_interval: float = 0.2,
    rss_reader: Callable[[int], float] = read_rss_mb,
) -> list[VariantResult]:
    """Launch each variant as a subprocess, capped at max_concurrent running at
    once. If max_total_rss_mb is set, also hold back launching a new variant
    (even under max_concurrent) once *currently running* processes' aggregate
    RSS already meets or exceeds that ceiling. This is necessarily reactive,
    not predictive — a variant's real memory use can't be known before it
    starts, so the ceiling can still be exceeded briefly right after a launch;
    it prevents runaway growth, not any single overshoot. At least one variant
    is always allowed to run regardless of the ceiling, so an unrealistically
    low value can't deadlock the whole batch. One variant's non-zero exit does
    not stop or affect the others.
    """
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be >= 1")

    pending = list(variants)
    running: dict[int, tuple[VariantSpec, subprocess.Popen, TextIO]] = {}
    results: list[VariantResult] = []

    def current_rss() -> float:
        return sum(rss_reader(proc.pid) for _, proc, _ in running.values())

    def launch(spec: VariantSpec) -> None:
        spec.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = spec.log_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(spec.command, stdout=log_file, stderr=subprocess.STDOUT)
        running[proc.pid] = (spec, proc, log_file)

    while pending or running:
        while pending and len(running) < max_concurrent:
            if max_total_rss_mb is not None and running and current_rss() >= max_total_rss_mb:
                break
            launch(pending.pop(0))

        if not running:
            time.sleep(poll_interval)
            continue

        time.sleep(poll_interval)
        finished_pids = [pid for pid, (_, proc, _) in running.items() if proc.poll() is not None]
        for pid in finished_pids:
            spec, proc, log_file = running.pop(pid)
            log_file.close()
            results.append(VariantResult(name=spec.name, returncode=proc.returncode, log_path=spec.log_path))

    return results
