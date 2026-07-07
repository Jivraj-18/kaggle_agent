import unittest
from pathlib import Path
from unittest.mock import patch

from kaggle_agent.gws_cli import CommandResult, drive_update, drive_upload


class DryRunPassthroughTests(unittest.TestCase):
    def test_drive_upload_appends_dry_run_flag(self):
        with patch("kaggle_agent.gws_cli.run_gws") as mock_run:
            mock_run.return_value = CommandResult([], 0, "{}", "")
            drive_upload(Path("README.md"), "readme.md", "folder-id", dry_run=True)
        args = mock_run.call_args[0][0]
        self.assertIn("--dry-run", args)

    def test_drive_upload_omits_dry_run_flag_by_default(self):
        with patch("kaggle_agent.gws_cli.run_gws") as mock_run:
            mock_run.return_value = CommandResult([], 0, "{}", "")
            drive_upload(Path("README.md"), "readme.md", "folder-id")
        args = mock_run.call_args[0][0]
        self.assertNotIn("--dry-run", args)

    def test_drive_update_appends_dry_run_flag(self):
        with patch("kaggle_agent.gws_cli.run_gws") as mock_run:
            mock_run.return_value = CommandResult([], 0, "{}", "")
            drive_update("file-id", Path("README.md"), "readme.md", dry_run=True)
        args = mock_run.call_args[0][0]
        self.assertIn("--dry-run", args)


if __name__ == "__main__":
    unittest.main()
