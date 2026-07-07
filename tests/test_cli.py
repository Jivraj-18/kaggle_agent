import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = os.environ.copy()
        env["KAGGLE_AGENT_STATE_DIR"] = self.tmp.name
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        return subprocess.run(
            [sys.executable, "-m", "kaggle_agent.cli", *args],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_summary_json(self):
        proc = self.run_cli("state-summary", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"competitions": 0', proc.stdout)
        self.assertIn('"scout_snapshots": 0', proc.stdout)

    def test_add_and_list_competition(self):
        add = self.run_cli("competitions", "add", "demo-comp", "--title", "Demo", "--decision", "join")
        self.assertEqual(add.returncode, 0, add.stderr)
        listing = self.run_cli("competitions", "list", "--decision", "join")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn('"slug": "demo-comp"', listing.stdout)
        self.assertIn('"decision": "join"', listing.stdout)

    def test_add_and_list_run(self):
        add = self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "demo-comp",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "1",
            "--status",
            "running",
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        listing = self.run_cli("runs", "list", "--pending")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn('"kernel_slug": "user/demo-kernel"', listing.stdout)

    def test_scout_competitions_from_file(self):
        source = Path(self.tmp.name) / "competitions.json"
        source.write_text(
            json.dumps(
                [
                    {
                        "ref": "https://www.kaggle.com/competitions/used-car-price-prediction",
                        "deadline": "2026-08-12T18:25:00",
                        "category": "Community",
                        "teamCount": 250,
                        "userHasEntered": False,
                    }
                ]
            )
        )
        proc = self.run_cli("scout-competitions", "--from-file", str(source), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("used-car-price-prediction", proc.stdout)
        history = json.loads((Path(self.tmp.name) / "scout_history.json").read_text())
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["items"][0]["slug"], "used-car-price-prediction")
        self.assertEqual(history[0]["items"][0]["raw"]["teamCount"], 250)
        self.assertIn("Review items[].raw directly", history[0]["agent_instruction"])


if __name__ == "__main__":
    unittest.main()
