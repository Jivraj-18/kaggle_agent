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


def drive_upload(path: Path, name: str, parent_id: str) -> CommandResult:
    return run_gws(
        [
            "drive",
            "+upload",
            str(path),
            "--parent",
            parent_id,
            "--name",
            name,
        ]
    )


def drive_update(file_id: str, path: Path, name: str) -> CommandResult:
    body = {"name": name}
    fields = "id,name,webViewLink,mimeType,modifiedTime,size"
    return run_gws(
        [
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
    )
