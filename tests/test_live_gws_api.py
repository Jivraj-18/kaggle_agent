"""Live Google Drive API smoke tests.

Same rationale as tests/test_live_kaggle_api.py: every stubbed test can only
prove "our code handles the shape we assumed," never that the shape is real.
The drive_upload fields-param bug (fixed alongside these tests) was found by
running dry-run calls against the real API, not by any stubbed test.

Skipped by default (needs network + gws credentials). Run explicitly before/
after touching kaggle_agent/gws_cli.py or kaggle_agent/drive_sync.py:

    KAGGLE_AGENT_LIVE_TESTS=1 uv run pytest tests/test_live_gws_api.py -v

`drive_upload`/`drive_update` are called with dry_run=True here, which
validates the real API by asking Drive to check the request without
executing it (`--dry-run`) — so this never creates or modifies a real file.
"""

import json
import os
import unittest
from pathlib import Path

from kaggle_agent.gws_cli import drive_update, drive_upload

LIVE = os.environ.get("KAGGLE_AGENT_LIVE_TESTS") == "1"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "drive.json"


@unittest.skipUnless(LIVE, "set KAGGLE_AGENT_LIVE_TESTS=1 to run live Google Drive API smoke tests")
class LiveGwsApiTests(unittest.TestCase):
    def setUp(self):
        self.folder_id = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["archive_folder_id"]
        self.sample_file = Path(__file__).resolve().parents[1] / "README.md"

    def test_drive_upload_dry_run_is_accepted_by_the_real_api(self):
        result = drive_upload(self.sample_file, "live-smoke-test.md", self.folder_id, dry_run=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        self.assertTrue(body.get("dry_run"))
        query_param_names = [pair[0] for pair in body.get("query_params", [])]
        self.assertIn("fields", query_param_names)

    def test_drive_update_dry_run_is_accepted_by_the_real_api(self):
        result = drive_update("nonexistent-file-id-for-dry-run", self.sample_file, "live-smoke-test.md", dry_run=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        self.assertTrue(body.get("dry_run"))


if __name__ == "__main__":
    unittest.main()
