import json
import tempfile
import unittest
from pathlib import Path

from kaggle_agent.prompt_history import (
    all_claude_prompts,
    append_prompt,
    claude_project_slug,
    claude_sessions_for_project,
    codex_sessions_for_cwd,
    extract_text,
    latest_claude_prompt,
)


class ClaudeProjectSlugTests(unittest.TestCase):
    def test_replaces_slashes_and_underscores_with_hyphens(self):
        # Verified live: Claude Code's actual project directory naming replaces
        # BOTH "/" and "_" with "-" (confirmed against multiple real
        # ~/.claude/projects/ entries, e.g. .../mlp_t2_2026_project became
        # ...-mlp-t2-2026-project). A naive .replace("/", "-") alone produces a
        # path that never matches the real directory.
        self.assertEqual(
            claude_project_slug(Path("/home/jivraj/experiments/kaggle_agent")),
            "-home-jivraj-experiments-kaggle-agent",
        )
        self.assertEqual(
            claude_project_slug(Path("/home/jivraj/experiments/mlp_t2_2026_project")),
            "-home-jivraj-experiments-mlp-t2-2026-project",
        )


class ExtractTextTests(unittest.TestCase):
    def test_plain_string_content(self):
        self.assertEqual(extract_text("hello there"), "hello there")

    def test_list_of_text_blocks(self):
        self.assertEqual(
            extract_text([{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]),
            "hello\nworld",
        )

    def test_filters_synthetic_local_command_output(self):
        self.assertIsNone(extract_text("<local-command-stdout>Set model to Fable 5</local-command-stdout>"))

    def test_filters_codex_environment_context(self):
        self.assertIsNone(extract_text("<environment_context>\n  <cwd>/x</cwd>\n</environment_context>"))

    def test_filters_codex_turn_aborted(self):
        # Found live syncing real Codex sessions: an interrupted turn injects
        # this as a synthetic "user" message, not a real prompt.
        self.assertIsNone(
            extract_text("<turn_aborted>\nThe user interrupted the previous turn on purpose.\n</turn_aborted>")
        )

    def test_filters_claude_task_notification(self):
        # Found live: after a session resume, a background-task notification
        # gets appended as a "user" type entry before the human's own message.
        self.assertIsNone(extract_text("<task-notification>\n<task-id>abc</task-id>\n</task-notification>"))

    def test_empty_or_whitespace_returns_none(self):
        self.assertIsNone(extract_text("   "))
        self.assertIsNone(extract_text(""))


class LatestClaudePromptTests(unittest.TestCase):
    def write_transcript(self, rows: list[dict]) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        for row in rows:
            tmp.write(json.dumps(row) + "\n")
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_returns_last_non_meta_user_prompt(self):
        path = self.write_transcript(
            [
                {"type": "user", "isMeta": True, "message": {"content": "<local-command-caveat>...</local-command-caveat>"}},
                {"type": "user", "message": {"content": "first real prompt"}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "reply"}]}},
                {"type": "user", "message": {"content": "second real prompt"}},
            ]
        )
        self.assertEqual(latest_claude_prompt(path), "second real prompt")

    def test_all_claude_prompts_returns_every_real_prompt_in_order(self):
        # The live UserPromptSubmit hook can silently not fire (found live: a
        # background-job session started with .claude/settings.json already
        # present still didn't trigger it) — all_claude_prompts backs a sync
        # fallback that backfills every prompt in a session, not just the
        # latest, matching what sync-codex already does for Codex.
        path = self.write_transcript(
            [
                {"type": "user", "isMeta": True, "message": {"content": "<local-command-caveat>...</local-command-caveat>"}},
                {"type": "user", "message": {"content": "first real prompt"}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "reply"}]}},
                {"type": "user", "message": {"content": "second real prompt"}},
            ]
        )
        self.assertEqual(all_claude_prompts(path), ["first real prompt", "second real prompt"])

    def test_all_claude_prompts_missing_file_returns_empty_list(self):
        self.assertEqual(all_claude_prompts(Path("/nonexistent/transcript.jsonl")), [])

    def test_missing_file_returns_none(self):
        self.assertIsNone(latest_claude_prompt(Path("/nonexistent/transcript.jsonl")))

    def test_no_user_messages_returns_none(self):
        path = self.write_transcript([{"type": "assistant", "message": {"content": "hi"}}])
        self.assertIsNone(latest_claude_prompt(path))


class ClaudeSessionsForProjectTests(unittest.TestCase):
    def test_lists_session_ids_and_prompts_under_project_slug_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp)
            slug_dir = projects_dir / "-home-x-proj"
            slug_dir.mkdir()
            (slug_dir / "session-a.jsonl").write_text(
                json.dumps({"type": "user", "message": {"content": "prompt from session a"}}) + "\n",
                encoding="utf-8",
            )
            (slug_dir / "session-b.jsonl").write_text(
                json.dumps({"type": "user", "message": {"content": "prompt from session b"}}) + "\n",
                encoding="utf-8",
            )
            results = claude_sessions_for_project(projects_dir, "-home-x-proj")
            by_id = {r["session_id"]: r["prompts"] for r in results}
            self.assertEqual(by_id, {"session-a": ["prompt from session a"], "session-b": ["prompt from session b"]})

    def test_missing_project_dir_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(claude_sessions_for_project(Path(tmp), "-nonexistent-slug"), [])


class CodexSessionsForCwdTests(unittest.TestCase):
    def test_finds_sessions_matching_cwd_and_extracts_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = Path(tmp)
            session_file = sessions_dir / "rollout-test-019abc.jsonl"
            session_file.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {"type": "session_meta", "payload": {"id": "019abc", "cwd": "/home/x/proj"}},
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": "<environment_context>skip me</environment_context>"}],
                            },
                        },
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": "real codex prompt"}],
                            },
                        },
                        {
                            "type": "response_item",
                            "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "reply"}]},
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            other_file = sessions_dir / "rollout-other-019xyz.jsonl"
            other_file.write_text(
                json.dumps({"type": "session_meta", "payload": {"id": "019xyz", "cwd": "/home/x/other-proj"}}) + "\n",
                encoding="utf-8",
            )

            results = codex_sessions_for_cwd(sessions_dir, "/home/x/proj")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["session_id"], "019abc")
            self.assertEqual(results[0]["prompts"], ["real codex prompt"])


class AppendPromptTests(unittest.TestCase):
    def test_creates_new_session_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "prompt_history.md"
            append_prompt(md_path, harness="claude", session_id="abc123", date="2026-07-08", prompt="first prompt")
            text = md_path.read_text(encoding="utf-8")
            self.assertIn("claude", text)
            self.assertIn("abc123", text)
            self.assertIn("claude --resume abc123", text)
            self.assertIn("first prompt", text)

    def test_appends_to_existing_session_section_without_duplicating_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "prompt_history.md"
            append_prompt(md_path, harness="claude", session_id="abc123", date="2026-07-08", prompt="first prompt")
            append_prompt(md_path, harness="claude", session_id="abc123", date="2026-07-08", prompt="second prompt")
            text = md_path.read_text(encoding="utf-8")
            self.assertEqual(text.count("claude --resume abc123"), 1)
            self.assertIn("first prompt", text)
            self.assertIn("second prompt", text)

    def test_skips_exact_duplicate_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "prompt_history.md"
            append_prompt(md_path, harness="claude", session_id="abc123", date="2026-07-08", prompt="same prompt")
            append_prompt(md_path, harness="claude", session_id="abc123", date="2026-07-08", prompt="same prompt")
            text = md_path.read_text(encoding="utf-8")
            self.assertEqual(text.count("same prompt"), 1)

    def test_codex_uses_resume_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "prompt_history.md"
            append_prompt(md_path, harness="codex", session_id="019abc", date="2026-07-08", prompt="a codex prompt")
            text = md_path.read_text(encoding="utf-8")
            self.assertIn("codex resume 019abc", text)


if __name__ == "__main__":
    unittest.main()
