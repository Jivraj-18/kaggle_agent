import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        return json.loads(self.stdout or "{}")


def run_gws(args: list[str]) -> CommandResult:
    proc = subprocess.run(
        ["gws", *args],
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        check=False,
    )
    return CommandResult(["gws", *args], proc.returncode, proc.stdout, proc.stderr)


def drive_upload(path: Path, name: str, parent_id: str, dry_run: bool = False) -> CommandResult:
    # Uses the raw `files create` method rather than the `+upload` shorthand: the
    # shorthand sends no `fields` query param (confirmed live via --dry-run), so
    # newly created files would silently get webViewLink/mimeType/etc. as null
    # forever. `drive_update` already did it this way for existing files; match it
    # so created and updated manifest entries carry the same fields.
    body = {"name": name, "parents": [parent_id]}
    fields = "id,name,webViewLink,mimeType,modifiedTime,size"
    args = [
        "drive",
        "files",
        "create",
        "--upload",
        str(path),
        "--json",
        json.dumps(body),
        "--params",
        json.dumps({"fields": fields}),
    ]
    if dry_run:
        args.append("--dry-run")
    return run_gws(args)


def drive_update(file_id: str, path: Path, name: str, dry_run: bool = False) -> CommandResult:
    body = {"name": name}
    fields = "id,name,webViewLink,mimeType,modifiedTime,size"
    args = [
        "drive",
        "files",
        "update",
        "--upload",
        str(path),
        "--json",
        json.dumps(body),
        "--params",
        json.dumps({"fileId": file_id, "fields": fields}),
    ]
    if dry_run:
        args.append("--dry-run")
    return run_gws(args)
