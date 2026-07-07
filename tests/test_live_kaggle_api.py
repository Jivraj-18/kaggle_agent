"""Live Kaggle API smoke tests.

These hit the real Kaggle API (read-only) to catch response-shape drift that
stubbed tests structurally cannot: every other Kaggle-touching test replaces
`uvx kaggle` with a fake script that returns hand-written JSON, so they only
prove "our code handles the shape we assumed" — never "that shape is real."
`parse_json_output`'s pagination-banner handling was added after exactly this
kind of drift was found by running these calls for real.

Skipped by default (slow, needs network + ~/.kaggle/credentials.json, and
real API responses can change). Run explicitly before/after touching
kaggle_cli.py or when investigating suspected schema drift:

    KAGGLE_AGENT_LIVE_TESTS=1 uv run pytest tests/test_live_kaggle_api.py -v

Uses the one real competition already tracked in state
(heavy-equipment-selling-price-prediction-challenge) and read-only endpoints
only. Never calls kernel_push, kernel_output, or competition_submit here —
those mutate real Kaggle state and are out of scope for a smoke test.
"""

import os
import unittest

from kaggle_agent.kaggle_cli import (
    competition_leaderboard,
    competition_submissions,
    kernel_status,
    list_competitions,
    parse_json_output,
)

LIVE = os.environ.get("KAGGLE_AGENT_LIVE_TESTS") == "1"
COMPETITION_SLUG = "heavy-equipment-selling-price-prediction-challenge"
KNOWN_KERNEL_SLUG = "jivrajsingh/22f3002542-notebook-2026t2"


@unittest.skipUnless(LIVE, "set KAGGLE_AGENT_LIVE_TESTS=1 to run live Kaggle API smoke tests")
class LiveKaggleApiTests(unittest.TestCase):
    def test_leaderboard_parses_and_has_expected_fields(self):
        result = competition_leaderboard(COMPETITION_SLUG, page_size=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_json_output(result.stdout, default=[])
        self.assertGreater(len(rows), 0)
        for key in ("teamId", "teamName", "score"):
            self.assertIn(key, rows[0])

    def test_submissions_parses_and_has_expected_fields(self):
        result = competition_submissions(COMPETITION_SLUG)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = parse_json_output(result.stdout, default=[])
        self.assertGreater(len(rows), 0)
        for key in ("ref", "fileName", "status", "publicScore"):
            self.assertIn(key, rows[0])

    def test_competitions_list_parses_and_has_expected_fields(self):
        rows, result = list_competitions("general", page_size=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(len(rows), 0)
        for key in ("ref", "deadline", "category"):
            self.assertIn(key, rows[0])

    def test_kernel_status_normalizes_to_bare_enum_value(self):
        status, result = kernel_status(KNOWN_KERNEL_SLUG)
        self.assertEqual(result.returncode, 0, result.stderr)
        # cli.check_run strips this prefix before writing runs.json; assert the
        # raw wrapper still returns the prefixed form so that strip doesn't
        # silently become a no-op if Kaggle changes the status string format.
        self.assertTrue(status.startswith("KernelWorkerStatus."))


if __name__ == "__main__":
    unittest.main()
