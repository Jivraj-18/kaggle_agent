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
        self.assertIn('"artifacts": 0', proc.stdout)
        self.assertIn('"competitions": 0', proc.stdout)
        self.assertIn('"experiments": 0', proc.stdout)
        self.assertIn('"notebooks": 0', proc.stdout)
        self.assertIn('"scout_snapshots": 0', proc.stdout)

    def test_resume_context_json_is_agent_entrypoint(self):
        self.run_cli("runs", "add", "--competition-slug", "demo", "--kernel-slug", "u/k", "--status", "running")
        proc = self.run_cli("resume-context", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual(body["summary"]["pending_runs"], 1)
        self.assertEqual(body["pending_runs"][0]["kernel_slug"], "u/k")
        self.assertIn("state_files", body)
        self.assertIn("state/runs.json", body["state_files"])

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

    def test_experiment_duplicate_is_blocked(self):
        plan = Path(self.tmp.name) / "plan.md"
        notebook = Path(self.tmp.name) / "notebook.py"
        plan.write_text("hypothesis: catboost with grouped folds\n", encoding="utf-8")
        notebook.write_text("print('write submission.csv')\n", encoding="utf-8")

        first = self.run_cli(
            "experiments",
            "add",
            "--competition-slug",
            "demo-comp",
            "--phase",
            "feature_engineering",
            "--hypothesis",
            "CatBoost with grouped folds improves CV",
            "--plan-file",
            str(plan),
            "--notebook-file",
            str(notebook),
            "--status",
            "planned",
            "--json",
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        first_body = json.loads(first.stdout)
        self.assertEqual(first_body["competition_slug"], "demo-comp")
        self.assertEqual(first_body["phase"], "feature_engineering")
        self.assertIn("experiment_key", first_body)

        second = self.run_cli(
            "experiments",
            "add",
            "--competition-slug",
            "demo-comp",
            "--hypothesis",
            "CatBoost with grouped folds improves CV",
            "--plan-file",
            str(plan),
            "--notebook-file",
            str(notebook),
            "--json",
        )
        self.assertEqual(second.returncode, 1)
        self.assertIn("duplicate experiment", second.stderr)
        self.assertIn(first_body["experiment_id"], second.stderr)

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
