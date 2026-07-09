import json
import tempfile
import unittest
from pathlib import Path

from kaggle_agent.langfuse_sync import discover_sessions, pair_turns


class PairTurnsTests(unittest.TestCase):
    def test_pairs_user_then_assistant_into_one_exchange(self):
        turns = [
            {"role": "user", "text": "hello", "model": None, "timestamp": "t1"},
            {"role": "assistant", "text": "hi there", "model": "claude-sonnet-5", "timestamp": "t2"},
        ]
        self.assertEqual(
            pair_turns(turns),
            [{"input": "hello", "output": "hi there", "model": "claude-sonnet-5", "timestamp": "t1"}],
        )

    def test_trailing_user_turn_with_no_reply_becomes_input_only_exchange(self):
        # Session ended (or was interrupted) before the assistant replied --
        # don't silently drop the prompt.
        turns = [
            {"role": "user", "text": "hello", "model": None, "timestamp": "t1"},
            {"role": "assistant", "text": "hi there", "model": "claude-sonnet-5", "timestamp": "t2"},
            {"role": "user", "text": "one more thing", "model": None, "timestamp": "t3"},
        ]
        self.assertEqual(
            pair_turns(turns)[-1],
            {"input": "one more thing", "output": None, "model": None, "timestamp": "t3"},
        )

    def test_multiple_assistant_turns_before_next_user_merge_into_one_output(self):
        # A single logical reply can span several assistant JSONL rows
        # (text between tool calls) -- all of it belongs to the same
        # exchange as the user prompt that triggered it, not separate rows.
        turns = [
            {"role": "user", "text": "do the thing", "model": None, "timestamp": "t1"},
            {"role": "assistant", "text": "starting on it", "model": "claude-sonnet-5", "timestamp": "t2"},
            {"role": "assistant", "text": "done", "model": "claude-sonnet-5", "timestamp": "t3"},
        ]
        self.assertEqual(
            pair_turns(turns),
            [{"input": "do the thing", "output": "starting on it\ndone", "model": "claude-sonnet-5", "timestamp": "t1"}],
        )


class DiscoverSessionsTests(unittest.TestCase):
    def test_finds_real_transcripts_and_enriches_with_matching_session_record(self):
        # sessions.jsonl is known to drift/miss real sessions (see
        # docs/architecture.md#observability) -- the actual transcript files
        # on disk are the source of truth for *which* sessions exist;
        # sessions.jsonl only supplies extra metadata when a record matches.
        from kaggle_agent.prompt_history import claude_project_slug

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "proj"
            project_root.mkdir()
            claude_dir = root / "claude-projects"
            slug_dir = claude_dir / claude_project_slug(project_root)
            slug_dir.mkdir(parents=True)
            (slug_dir / "sess-a.jsonl").write_text(
                json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n", encoding="utf-8"
            )
            codex_dir = root / "codex-sessions"
            codex_dir.mkdir()
            (codex_dir / "rollout-sess-b.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "session_meta", "payload": {"id": "sess-b", "cwd": str(project_root)}}),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi codex"}]},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            sessions = discover_sessions(
                project_root=project_root,
                session_records=[{"session_id": "sess-a", "harness": "claude", "model": "claude-sonnet-5", "outcome": "did the thing"}],
                claude_projects_dir=claude_dir,
                codex_sessions_dir=codex_dir,
            )

            by_id = {s["session_id"]: s for s in sessions}
            self.assertEqual(by_id["sess-a"]["model"], "claude-sonnet-5")
            self.assertEqual(by_id["sess-a"]["outcome"], "did the thing")
            self.assertEqual(by_id["sess-a"]["harness"], "claude")
            self.assertEqual(by_id["sess-b"]["harness"], "codex")
            self.assertNotIn("model", by_id["sess-b"])  # no matching sessions.jsonl record


if __name__ == "__main__":
    unittest.main()
