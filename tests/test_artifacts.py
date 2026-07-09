import os
import tempfile
import unittest
from pathlib import Path


class ReviewOutputArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["KAGGLE_AGENT_STATE_DIR"] = self.tmp.name
        import kaggle_agent.artifacts as artifacts
        import kaggle_agent.config as config
        import kaggle_agent.state as state

        config.STATE_DIR = Path(self.tmp.name)
        state.STATE_DIR = Path(self.tmp.name)
        state.ensure_state_files()
        self.artifacts = artifacts
        self.run = {"run_id": "run-1", "competition_slug": "demo", "experiment_key": "exp-key"}

    def tearDown(self):
        os.environ.pop("KAGGLE_AGENT_STATE_DIR", None)
        self.tmp.cleanup()

    def _artifact(self, filename):
        return {
            "artifact_id": "artifact-1",
            "run_id": "run-1",
            "local_path": self.tmp.name,
            "files": [{"name": filename, "size": 10, "sha256": "abc"}],
        }

    def test_batch_variant_submission_filename_is_recognized(self):
        # exp002.py, exp003.py etc write submission_<variant>.csv per the
        # repo's unique-filename-per-batch-variant convention (agents/developer.md).
        # review_output_artifact used to only check for the literal name
        # "submission.csv", so every real batch candidate would fail
        # submission_csv_present even though the file was fine.
        review = self.artifacts.review_output_artifact(self.run, self._artifact("submission_exp002.csv"))
        self.assertIn("submission_csv_present", review["passed_checks"])
        self.assertIn("submission_csv_nonempty", review["passed_checks"])
        self.assertEqual(review["verdict"], "submission_candidate")

    def test_plain_submission_csv_still_recognized(self):
        review = self.artifacts.review_output_artifact(self.run, self._artifact("submission.csv"))
        self.assertIn("submission_csv_present", review["passed_checks"])
        self.assertEqual(review["verdict"], "submission_candidate")

    def test_missing_submission_csv_fails(self):
        review = self.artifacts.review_output_artifact(self.run, self._artifact("predictions.csv"))
        self.assertIn("submission_csv_present", review["failed_checks"])
        self.assertEqual(review["verdict"], "invalid_output")

    def test_ambiguous_multiple_submission_files_fails(self):
        artifact = {
            "artifact_id": "artifact-1",
            "run_id": "run-1",
            "local_path": self.tmp.name,
            "files": [
                {"name": "submission_exp002.csv", "size": 10, "sha256": "abc"},
                {"name": "submission_exp003.csv", "size": 10, "sha256": "def"},
            ],
        }
        review = self.artifacts.review_output_artifact(self.run, artifact)
        self.assertIn("submission_csv_ambiguous", review["failed_checks"])
        self.assertEqual(review["verdict"], "invalid_output")


if __name__ == "__main__":
    unittest.main()
