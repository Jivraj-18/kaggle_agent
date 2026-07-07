import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DriveSyncCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.bin = self.root / "bin"
        self.config = self.root / "drive.json"
        self.calls = self.root / "gws-calls.jsonl"
        self.bin.mkdir()
        self.config.write_text(
            json.dumps(
                {
                    "archive_folder_id": "drive-folder",
                    "roots": [str(self.state)],
                }
            ),
            encoding="utf-8",
        )
        self._write_fake_gws()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_fake_gws(self):
        script = self.bin / "gws"
        script.write_text(
            """#!/usr/bin/env python3
import hashlib
import json
import os
import sys

args = sys.argv[1:]
upload = args[args.index("--upload") + 1] if "--upload" in args else args[2]
payload = json.loads(args[args.index("--json") + 1]) if "--json" in args else {}
params = json.loads(args[args.index("--params") + 1]) if "--params" in args else {}
name = payload.get("name") or args[args.index("--name") + 1]
file_id = params.get("fileId") or "id-" + hashlib.sha1(name.encode()).hexdigest()[:10]
with open(os.environ["GWS_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"args": args, "upload": upload, "name": name, "file_id": file_id}) + "\\n")
print(json.dumps({"id": file_id, "name": name, "webViewLink": "https://drive.test/" + file_id}))
""",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

    def run_cli(self):
        env = os.environ.copy()
        env["KAGGLE_AGENT_STATE_DIR"] = str(self.state)
        env["GWS_CALLS"] = str(self.calls)
        env["PATH"] = f"{self.bin}{os.pathsep}{env['PATH']}"
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "kaggle_agent.cli",
                "drive-sync",
                "push",
                "--config",
                str(self.config),
                "--json",
            ],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_push_uploads_changed_state_and_skips_unchanged_files(self):
        first = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        first_body = json.loads(first.stdout)
        self.assertGreaterEqual(len(first_body["created"]), 6)
        self.assertEqual(first_body["updated"], [])
        self.assertEqual(first_body["errors"], [])
        self.assertTrue((self.state / "drive_manifest.json").exists())

        second = self.run_cli()
        self.assertEqual(second.returncode, 0, second.stderr)
        second_body = json.loads(second.stdout)
        self.assertEqual(second_body["created"], [])
        self.assertEqual(second_body["updated"], [])
        self.assertGreaterEqual(len(second_body["skipped"]), 6)

        calls = self.calls.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(calls), len(first_body["created"]))

    def test_push_upload_requests_web_view_link_field(self):
        # drive_update already asked for `fields` including webViewLink; drive_upload
        # (new-file path) used the `+upload` shorthand, which sends no `fields` param
        # at all — verified live against the real gws CLI via --dry-run. New uploads
        # would silently get drive_web_url: null forever. Assert the actual request
        # shape here so a regression shows up without needing a live call.
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.calls.read_text(encoding="utf-8").strip().splitlines()]
        self.assertGreater(len(calls), 0)
        for call in calls:
            args = call["args"]
            self.assertIn("--params", args)
            params = json.loads(args[args.index("--params") + 1])
            self.assertIn("webViewLink", params.get("fields", ""))

    def test_push_updates_existing_drive_file_when_state_changes(self):
        first = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        manifest = json.loads((self.state / "drive_manifest.json").read_text(encoding="utf-8"))
        previous_id = manifest["state/preferences.json"]["drive_file_id"]
        previous_calls = self.calls.read_text(encoding="utf-8").strip().splitlines()

        preferences = json.loads((self.state / "preferences.json").read_text(encoding="utf-8"))
        preferences["prefer"].append("fast baseline first")
        (self.state / "preferences.json").write_text(json.dumps(preferences), encoding="utf-8")

        second = self.run_cli()
        self.assertEqual(second.returncode, 0, second.stderr)
        body = json.loads(second.stdout)
        self.assertEqual(body["created"], [])
        self.assertEqual(len(body["updated"]), 1)
        self.assertEqual(body["updated"][0]["local_path"], "state/preferences.json")
        self.assertEqual(body["updated"][0]["drive_file_id"], previous_id)

        calls = self.calls.read_text(encoding="utf-8").strip().splitlines()
        update_call = json.loads(calls[-1])
        self.assertEqual(len(calls), len(previous_calls) + 1)
        self.assertIn("files", update_call["args"])
        self.assertIn("update", update_call["args"])


if __name__ == "__main__":
    unittest.main()
