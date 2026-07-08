"""Push this as a Kaggle kernel to re-verify real CPU/RAM/disk limits.

Kaggle's kernel resource allocation can change over time (image updates,
tier changes) — don't trust the numbers in SKILL.md forever; re-run this
and diff. Push with a kernel-metadata.json like:

{
  "id": "<you>/kaggle-resource-probe",
  "title": "Kaggle resource probe",
  "code_file": "probe_kernel_resources.py",
  "language": "python",
  "kernel_type": "script",
  "is_private": true,
  "enable_gpu": false,
  "enable_internet": false,
  "dataset_sources": [],
  "competition_sources": [],
  "kernel_sources": []
}

SECURITY: never widen the env var filter below to match plain "KAGGLE" —
Kaggle injects real per-session secrets (KAGGLE_DATA_PROXY_TOKEN,
KAGGLE_USER_SECRETS_TOKEN) into every kernel's environment. A first version
of this script matched on "KAGGLE" alone and printed real tokens into a
downloaded kernel log. Print variable *names* only, never values, for
anything that isn't explicitly known-safe.
"""

import multiprocessing
import os
import shutil
import subprocess

SAFE_ENV_PREFIXES = ("KAGGLE_DOCKER_IMAGE", "KAGGLE_KERNEL_RUN_TYPE", "KAGGLE_GCP_ZONE", "KAGGLE_URL_BASE")
SENSITIVE_MARKERS = ("TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL")


def main() -> None:
    print("=== CPU ===")
    print("os.cpu_count():", os.cpu_count())
    print("multiprocessing.cpu_count():", multiprocessing.cpu_count())
    try:
        with open("/proc/cpuinfo") as f:
            print("physical cores (cpuinfo):", f.read().count("processor\t:"))
    except OSError as e:
        print("cpuinfo read failed:", e)

    print("=== Memory ===")
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith(("MemTotal", "MemAvailable")):
                    print(line.strip())
    except OSError as e:
        print("meminfo read failed:", e)

    print("=== Disk ===")
    for path in ("/kaggle/working", "/kaggle/input", "/"):
        try:
            usage = shutil.disk_usage(path)
            print(f"{path}: total={round(usage.total / 1e9, 2)}GB free={round(usage.free / 1e9, 2)}GB")
        except OSError as e:
            print(path, "failed:", e)

    print("=== GPU ===")
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        print("nvidia-smi returncode:", result.returncode)
    except FileNotFoundError:
        print("nvidia-smi not present (expected on a CPU-only kernel)")

    print("=== env var names only (never print values — see SECURITY note above) ===")
    for key in sorted(os.environ):
        if "KAGGLE" not in key.upper():
            continue
        if any(marker in key.upper() for marker in SENSITIVE_MARKERS):
            print(f"{key}=<redacted, sensitive>")
        else:
            print(key)


if __name__ == "__main__":
    main()
