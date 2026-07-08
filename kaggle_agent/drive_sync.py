import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .config import PROJECT_ROOT, STATE_DIR
from .gws_cli import CommandResult, drive_update, drive_upload
from .state import utc_now

SKIP_DIRS = {".git", ".pytest_cache", ".venv", "__pycache__", "data"}
# "data" specifically: competitions/<slug>/data/ holds large, re-downloadable
# raw Kaggle files (train.csv, zips) - re-fetchable from Kaggle any time, not
# worth Drive quota/upload time. Plans/notebooks/kernel files still sync.
SKIP_FILES = {".DS_Store", "drive_manifest.json"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_root(root: Path) -> Path:
    return (root if root.is_absolute() else PROJECT_ROOT / root).resolve()


def local_path_for(path: Path, root: Path) -> str:
    if path.is_relative_to(PROJECT_ROOT):
        return str(path.relative_to(PROJECT_ROOT))
    return str(Path(root.name) / path.relative_to(root))


def iter_files(root: Path) -> list[Path]:
    actual = resolve_root(root)
    files: list[Path] = []
    for path in sorted(actual.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(actual).parts
        if any(part in SKIP_DIRS for part in rel) or path.name in SKIP_FILES:
            continue
        files.append(path)
    return files


def drive_name(local_path: str) -> str:
    return local_path.replace("/", "__")


def load_manifest() -> dict[str, dict[str, Any]]:
    path = STATE_DIR / "drive_manifest.json"
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return {str(row["local_path"]): row for row in value}
    return value


def save_manifest(manifest: dict[str, dict[str, Any]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / "drive_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def push_roots(
    roots: list[str],
    folder_id: str,
    uploader: Callable[[Path, str, str], CommandResult] = drive_upload,
    updater: Callable[[str, Path, str], CommandResult] = drive_update,
) -> dict[str, Any]:
    manifest = load_manifest()
    summary: dict[str, Any] = {
        "folder_id": folder_id,
        "created": [],
        "updated": [],
        "skipped": [],
        "errors": [],
    }

    for root in roots:
        actual_root = resolve_root(Path(root))
        for path in iter_files(actual_root):
            local_path = local_path_for(path, actual_root)
            digest = sha256_file(path)
            previous = manifest.get(local_path)
            if previous and previous.get("sha256") == digest:
                summary["skipped"].append(local_path)
                continue

            name = drive_name(local_path)
            if previous and previous.get("drive_file_id"):
                result = updater(str(previous["drive_file_id"]), path, name)
                bucket = "updated"
            else:
                result = uploader(path, name, folder_id)
                bucket = "created"

            if result.returncode != 0:
                summary["errors"].append(
                    {
                        "local_path": local_path,
                        "returncode": result.returncode,
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                    }
                )
                continue

            remote = result.json()
            manifest[local_path] = {
                "local_path": local_path,
                "drive_name": name,
                "drive_file_id": remote.get("id"),
                "drive_web_url": remote.get("webViewLink"),
                "sha256": digest,
                "size": path.stat().st_size,
                "last_uploaded_at": utc_now(),
                "remote": remote,
            }
            summary[bucket].append(manifest[local_path])

    save_manifest(manifest)
    return summary
