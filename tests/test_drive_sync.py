import tempfile
import unittest
from pathlib import Path

from kaggle_agent.drive_sync import iter_files


class IterFilesTests(unittest.TestCase):
    def test_skips_data_directories(self):
        """competitions/<slug>/data/ holds large, re-downloadable raw Kaggle
        files (train.csv, zips) - not worth syncing to Drive. Plans,
        notebooks, and kernel files under the same competition root should
        still sync."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comp = root / "competitions" / "some-slug"
            (comp / "data").mkdir(parents=True)
            (comp / "data" / "train.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            (comp / "plans").mkdir(parents=True)
            (comp / "plans" / "exp001.md").write_text("# plan", encoding="utf-8")

            files = iter_files(root / "competitions")
            rel_paths = {p.relative_to(root / "competitions") for p in files}

            self.assertIn(Path("some-slug/plans/exp001.md"), rel_paths)
            self.assertNotIn(Path("some-slug/data/train.csv"), rel_paths)
            self.assertFalse(any("data" in p.parts for p in rel_paths))


if __name__ == "__main__":
    unittest.main()
