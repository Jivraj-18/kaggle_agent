import json
import tempfile
import unittest
from pathlib import Path

from kaggle_agent.token_usage import parse_claude_transcript


class ParseClaudeTranscriptTests(unittest.TestCase):
    def write_transcript(self, rows: list[dict]) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        for row in rows:
            tmp.write(json.dumps(row) + "\n")
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_sums_usage_across_assistant_turns(self):
        path = self.write_transcript(
            [
                {"type": "user", "message": {"role": "user", "content": "hi"}},
                {
                    "type": "assistant",
                    "message": {
                        "model": "claude-sonnet-5",
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 20,
                            "cache_read_input_tokens": 50,
                            "cache_creation_input_tokens": 10,
                        },
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "model": "claude-sonnet-5",
                        "usage": {
                            "input_tokens": 200,
                            "output_tokens": 40,
                            "cache_read_input_tokens": 0,
                            "cache_creation_input_tokens": 0,
                        },
                    },
                },
            ]
        )
        totals = parse_claude_transcript(path)
        self.assertEqual(totals["input"], 300)
        self.assertEqual(totals["output"], 60)
        self.assertEqual(totals["cache_read"], 50)
        self.assertEqual(totals["cache_creation"], 10)
        self.assertEqual(totals["model"], "claude-sonnet-5")
        self.assertEqual(totals["assistant_turns"], 2)

    def test_ignores_non_assistant_and_usage_less_rows(self):
        path = self.write_transcript(
            [
                {"type": "user", "message": {"role": "user", "content": "hi"}},
                {"type": "assistant", "message": {"model": "claude-sonnet-5"}},
                {"type": "summary", "summary": "compacted"},
            ]
        )
        totals = parse_claude_transcript(path)
        self.assertEqual(totals["assistant_turns"], 0)
        self.assertEqual(totals["input"], 0)

    def test_skips_malformed_lines_without_raising(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        tmp.write(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "model": "claude-sonnet-5",
                        "usage": {"input_tokens": 5, "output_tokens": 1},
                    },
                }
            )
            + "\n"
        )
        tmp.write("{not valid json\n")
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        totals = parse_claude_transcript(Path(tmp.name))
        self.assertEqual(totals["assistant_turns"], 1)
        self.assertEqual(totals["input"], 5)

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            parse_claude_transcript(Path("/nonexistent/transcript.jsonl"))


if __name__ == "__main__":
    unittest.main()
