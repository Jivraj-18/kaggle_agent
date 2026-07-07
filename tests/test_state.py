import json
import os
import tempfile
import unittest
from pathlib import Path


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["KAGGLE_AGENT_STATE_DIR"] = self.tmp.name
        import kaggle_agent.config as config
        import kaggle_agent.state as state

        config.STATE_DIR = Path(self.tmp.name)
        state.STATE_DIR = Path(self.tmp.name)
        self.state = state

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("KAGGLE_AGENT_STATE_DIR", None)

    def test_ensure_state_files(self):
        self.state.ensure_state_files()
        self.assertTrue((Path(self.tmp.name) / "competitions.json").exists())
        self.assertTrue((Path(self.tmp.name) / "lessons.md").exists())
        self.assertEqual(self.state.validate_state(), [])

    def test_upsert_by_key_updates_existing_record(self):
        self.state.ensure_state_files()
        first = self.state.upsert_by_key("competitions.json", "slug", {"slug": "abc", "title": "Old"})
        second = self.state.upsert_by_key("competitions.json", "slug", {"slug": "abc", "title": "New"})
        rows = json.loads((Path(self.tmp.name) / "competitions.json").read_text())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "New")
        self.assertEqual(first["created_at"], second["created_at"])

    def test_validate_state_checks_known_enums(self):
        self.state.ensure_state_files()
        (Path(self.tmp.name) / "profiles.json").write_text(
            json.dumps(
                [
                    {
                        "competition_slug": "demo",
                        "metric_direction": "sideways",
                    }
                ]
            )
        )
        (Path(self.tmp.name) / "runs.json").write_text(
            json.dumps(
                [
                    {
                        "run_id": "run-1",
                        "failure_class": "mystery",
                    }
                ]
            )
        )
        errors = self.state.validate_state()
        self.assertIn("profiles.json[0].metric_direction: expected one of maximize, minimize", errors)
        self.assertIn("runs.json[0].failure_class: unknown failure class mystery", errors)

    def test_validate_state_checks_required_lineage_fields(self):
        self.state.ensure_state_files()
        (Path(self.tmp.name) / "experiments.json").write_text(json.dumps([{"competition_slug": "demo"}]))
        (Path(self.tmp.name) / "runs.json").write_text(json.dumps([{"run_id": "run-1"}]))
        (Path(self.tmp.name) / "submissions.json").write_text(json.dumps([{"submission_ref": "sub-1"}]))

        errors = self.state.validate_state()
        self.assertIn("experiments.json[0].experiment_key: missing required field", errors)
        self.assertIn("experiments.json[0].hypothesis: missing required field", errors)
        self.assertIn("runs.json[0].competition_slug: missing required field", errors)
        self.assertIn("submissions.json[0].competition_slug: missing required field", errors)


if __name__ == "__main__":
    unittest.main()
