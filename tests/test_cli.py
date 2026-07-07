import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def run_cli(self, *args, env_overrides=None):
        env = os.environ.copy()
        env["KAGGLE_AGENT_STATE_DIR"] = self.tmp.name
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        if env_overrides:
            env.update(env_overrides)
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
        self.run_cli("tasks", "add", "--task-id", "task-1", "--competition-slug", "demo", "--kind", "review_outputs")
        proc = self.run_cli("resume-context", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual(body["summary"]["pending_runs"], 1)
        self.assertEqual(body["summary"]["open_tasks"], 1)
        self.assertEqual(body["pending_runs"][0]["kernel_slug"], "u/k")
        self.assertEqual(body["open_tasks"][0]["task_id"], "task-1")
        self.assertEqual(body["competition_status"]["demo"]["pending_runs"], 1)
        self.assertEqual(body["competition_status"]["demo"]["open_tasks"], 1)
        self.assertIn("check_status", body["competition_status"]["demo"]["next_actions"])
        self.assertIn("state_files", body)
        self.assertIn("state/runs.json", body["state_files"])
        self.assertIn("state/observability/sessions.jsonl", body["state_files"])

    def test_session_start_end_writes_observability_jsonl(self):
        start = self.run_cli(
            "sessions",
            "start",
            "--harness",
            "codex",
            "--model",
            "gpt-5",
            "--skill",
            "kaggle-check-updates",
            "--competition-slug",
            "demo-comp",
            "--json",
        )
        self.assertEqual(start.returncode, 0, start.stderr)
        session = json.loads(start.stdout)
        self.assertIn("session_id", session)

        end = self.run_cli(
            "sessions",
            "end",
            session["session_id"],
            "--outcome",
            "checked_pending_runs",
            "--personas",
            "reviewer",
            "summarizer",
            "--state-writes",
            "runs.json",
            "lessons.md",
            "--tokens-input",
            "1000",
            "--tokens-output",
            "200",
            "--tokens-cache-read",
            "300",
            "--token-source",
            "self-report",
            "--estimated-cost-usd",
            "0.12",
            "--human-interventions",
            "1",
            "--json",
        )
        self.assertEqual(end.returncode, 0, end.stderr)
        record = json.loads(end.stdout)
        self.assertEqual(record["session_id"], session["session_id"])
        self.assertEqual(record["outcome"], "checked_pending_runs")
        self.assertEqual(record["tokens"]["input"], 1000)
        self.assertEqual(record["personas_used"], ["reviewer", "summarizer"])

        jsonl = Path(self.tmp.name) / "observability" / "sessions.jsonl"
        lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["estimated_cost_usd"], 0.12)

    def test_session_end_reads_tokens_from_claude_transcript(self):
        start = self.run_cli(
            "sessions",
            "start",
            "--harness",
            "claude",
            "--model",
            "claude-sonnet-5",
            "--skill",
            "kaggle-check-updates",
            "--json",
        )
        session = json.loads(start.stdout)

        transcript = Path(self.tmp.name) / "transcript.jsonl"
        transcript.write_text(
            "\n".join(
                json.dumps(row)
                for row in [
                    {"type": "user", "message": {"role": "user", "content": "hi"}},
                    {
                        "type": "assistant",
                        "message": {
                            "model": "claude-sonnet-5",
                            "usage": {
                                "input_tokens": 400,
                                "output_tokens": 80,
                                "cache_read_input_tokens": 120,
                                "cache_creation_input_tokens": 30,
                            },
                        },
                    },
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        end = self.run_cli(
            "sessions",
            "end",
            session["session_id"],
            "--outcome",
            "checked_pending_runs",
            "--transcript-file",
            str(transcript),
            "--json",
        )
        self.assertEqual(end.returncode, 0, end.stderr)
        record = json.loads(end.stdout)
        self.assertEqual(record["tokens"]["input"], 400)
        self.assertEqual(record["tokens"]["output"], 80)
        self.assertEqual(record["tokens"]["cache_read"], 120)
        self.assertEqual(record["tokens"]["source"], "claude-transcript-parse")

    def test_add_and_list_competition(self):
        add = self.run_cli("competitions", "add", "demo-comp", "--title", "Demo", "--decision", "join")
        self.assertEqual(add.returncode, 0, add.stderr)
        listing = self.run_cli("competitions", "list", "--decision", "join")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn('"slug": "demo-comp"', listing.stdout)
        self.assertIn('"decision": "join"', listing.stdout)

    def test_add_and_list_competition_profile(self):
        add = self.run_cli(
            "profiles",
            "add",
            "demo-comp",
            "--problem-type",
            "tabular_regression",
            "--metric-name",
            "RMSLE",
            "--metric-direction",
            "minimize",
            "--submission-id-column",
            "id",
            "--submission-target-column",
            "target",
            "--internet-allowed",
            "false",
            "--external-data-allowed",
            "false",
            "--notes",
            "Reader extracted from rules.",
            "--team-name",
            "my-team",
            "--json",
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        profile = json.loads(add.stdout)
        self.assertEqual(profile["competition_slug"], "demo-comp")
        self.assertEqual(profile["metric_name"], "RMSLE")
        self.assertFalse(profile["internet_allowed"])
        self.assertEqual(profile["team_name"], "my-team")

        listing = self.run_cli("profiles", "list", "--competition-slug", "demo-comp", "--json")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        rows = json.loads(listing.stdout)
        self.assertEqual(rows[0]["submission_target_column"], "target")

    def test_add_and_list_run(self):
        add = self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
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
        self.assertIn('"experiment_key": "exp-key-1"', listing.stdout)
        self.assertIn('"kernel_slug": "user/demo-kernel"', listing.stdout)

    def test_add_and_list_notebook_reference(self):
        add = self.run_cli(
            "notebooks",
            "add",
            "--notebook-id",
            "nb-1",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "1",
            "--drive-file-id",
            "drive-123",
            "--source-sha256",
            "abc123",
            "--status",
            "pushed",
            "--json",
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        body = json.loads(add.stdout)
        self.assertEqual(body["drive_file_id"], "drive-123")
        self.assertEqual(body["experiment_key"], "exp-key-1")

        listing = self.run_cli("notebooks", "list", "--competition-slug", "demo-comp", "--json")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        rows = json.loads(listing.stdout)
        self.assertEqual(rows[0]["kernel_slug"], "user/demo-kernel")

    def test_validate_notebook_metadata_against_profile(self):
        self.run_cli(
            "profiles",
            "add",
            "demo-comp",
            "--internet-allowed",
            "false",
            "--json",
        )
        metadata = Path(self.tmp.name) / "kernel-metadata.json"
        metadata.write_text(
            json.dumps(
                {
                    "id": "user/demo-kernel",
                    "competition_sources": ["demo-comp"],
                    "enable_internet": False,
                }
            ),
            encoding="utf-8",
        )
        valid = self.run_cli(
            "notebooks",
            "validate-metadata",
            str(metadata),
            "--competition-slug",
            "demo-comp",
            "--json",
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertTrue(json.loads(valid.stdout)["ok"])

        metadata.write_text(
            json.dumps(
                {
                    "id": "user/demo-kernel",
                    "competition_sources": ["other-comp"],
                    "enable_internet": True,
                }
            ),
            encoding="utf-8",
        )
        invalid = self.run_cli(
            "notebooks",
            "validate-metadata",
            str(metadata),
            "--competition-slug",
            "demo-comp",
            "--json",
        )
        self.assertEqual(invalid.returncode, 1)
        body = json.loads(invalid.stdout)
        self.assertIn("competition_sources: missing demo-comp", body["errors"])
        self.assertIn("enable_internet: profile forbids internet", body["errors"])

    def test_push_notebook_records_notebook_and_run(self):
        notebook_dir = Path(self.tmp.name) / "kernel"
        notebook_dir.mkdir()
        (notebook_dir / "kernel-metadata.json").write_text(
            json.dumps({"id": "user/demo-kernel", "competition_sources": ["demo-comp"]}),
            encoding="utf-8",
        )
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        calls = Path(self.tmp.name) / "uvx-calls.jsonl"
        fake_uvx = bin_dir / "uvx"
        fake_uvx.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["UVX_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
print("Kernel push queued")
""",
            encoding="utf-8",
        )
        fake_uvx.chmod(0o755)

        pushed = self.run_cli(
            "notebooks",
            "push",
            "--path",
            str(notebook_dir),
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "2",
            "--json",
            env_overrides={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "UVX_CALLS": str(calls)},
        )
        self.assertEqual(pushed.returncode, 0, pushed.stderr)
        body = json.loads(pushed.stdout)
        self.assertEqual(body["run"]["run_id"], "user/demo-kernel:v2")
        self.assertEqual(body["notebook"]["status"], "pushed")
        call = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(call, ["kaggle", "kernels", "push", "-p", str(notebook_dir)])

        runs = json.loads((Path(self.tmp.name) / "runs.json").read_text(encoding="utf-8"))
        notebooks = json.loads((Path(self.tmp.name) / "notebooks.json").read_text(encoding="utf-8"))
        self.assertEqual(runs[0]["next_action"], "check_status")
        self.assertEqual(notebooks[0]["source_sha256"], body["notebook"]["source_sha256"])

    def test_push_notebook_blocks_invalid_metadata_before_kaggle_cli(self):
        notebook_dir = Path(self.tmp.name) / "kernel"
        notebook_dir.mkdir()
        (notebook_dir / "kernel-metadata.json").write_text(
            json.dumps({"id": "user/wrong-kernel", "competition_sources": ["other-comp"]}),
            encoding="utf-8",
        )
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        calls = Path(self.tmp.name) / "uvx-calls.jsonl"
        fake_uvx = bin_dir / "uvx"
        fake_uvx.write_text(
            """#!/usr/bin/env python3
import os
from pathlib import Path
Path(os.environ["UVX_CALLS"]).write_text("called", encoding="utf-8")
""",
            encoding="utf-8",
        )
        fake_uvx.chmod(0o755)

        pushed = self.run_cli(
            "notebooks",
            "push",
            "--path",
            str(notebook_dir),
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "2",
            "--json",
            env_overrides={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "UVX_CALLS": str(calls)},
        )
        self.assertEqual(pushed.returncode, 1)
        body = json.loads(pushed.stdout)
        self.assertIn("competition_sources: missing demo-comp", body["errors"])
        self.assertIn("id: expected user/demo-kernel", body["errors"])
        self.assertFalse(calls.exists())

    def test_add_list_and_complete_task(self):
        add = self.run_cli(
            "tasks",
            "add",
            "--task-id",
            "task-1",
            "--competition-slug",
            "demo-comp",
            "--kind",
            "review_outputs",
            "--priority",
            "high",
            "--notes",
            "Review pulled submission.",
            "--json",
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        task = json.loads(add.stdout)
        self.assertEqual(task["status"], "open")

        listing = self.run_cli("tasks", "list", "--status", "open", "--json")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn("review_outputs", listing.stdout)

        done = self.run_cli("tasks", "complete", "task-1", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "complete")

    def test_submission_records_experiment_lineage(self):
        add = self.run_cli(
            "submissions",
            "add",
            "--ref",
            "sub-1",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--public-score",
            "0.8",
            "--cv-score",
            "0.75",
            "--rank",
            "100",
            "--percentile",
            "0.9",
            "--valid",
            "--json",
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        body = json.loads(add.stdout)
        self.assertEqual(body["experiment_key"], "exp-key-1")
        self.assertEqual(body["cv_score"], 0.75)
        self.assertTrue(body["valid"])

    def test_submit_file_calls_kaggle_and_records_submission(self):
        submission = Path(self.tmp.name) / "submission.csv"
        submission.write_text("id,target\n1,0.5\n", encoding="utf-8")
        self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "2",
            "--status",
            "COMPLETE",
            "--next-action",
            "human_review_submission",
        )
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        calls = Path(self.tmp.name) / "uvx-calls.jsonl"
        fake_uvx = bin_dir / "uvx"
        fake_uvx.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["UVX_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
print("Successfully submitted to competition")
""",
            encoding="utf-8",
        )
        fake_uvx.chmod(0o755)

        submitted = self.run_cli(
            "submissions",
            "submit-file",
            "--competition-slug",
            "demo-comp",
            "--file",
            str(submission),
            "--message",
            "exp-key-1 candidate",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "2",
            "--json",
            env_overrides={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "UVX_CALLS": str(calls)},
        )
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        body = json.loads(submitted.stdout)
        self.assertEqual(body["submission"]["competition_slug"], "demo-comp")
        self.assertEqual(body["submission"]["experiment_key"], "exp-key-1")
        self.assertEqual(body["submission"]["status"], "submitted")
        self.assertTrue(body["submission"]["valid"])
        call = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(
            call,
            [
                "kaggle",
                "competitions",
                "submit",
                "-c",
                "demo-comp",
                "-f",
                str(submission),
                "-m",
                "exp-key-1 candidate",
            ],
        )
        rows = json.loads((Path(self.tmp.name) / "submissions.json").read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["file_sha256"], body["submission"]["file_sha256"])
        runs = json.loads((Path(self.tmp.name) / "runs.json").read_text(encoding="utf-8"))
        self.assertTrue(runs[0]["submitted"])
        self.assertEqual(runs[0]["next_action"], "check_leaderboard")

    def test_submit_file_uses_real_kaggle_ref_to_avoid_duplicate_on_refresh(self):
        # Found live: submit-file invented a local ref (competition:sha256[:12]),
        # but a later `submissions refresh` matches by Kaggle's own numeric ref,
        # creating a second, disconnected row for the same real submission. Look
        # up the real ref right after submitting so both write to the same row.
        submission = Path(self.tmp.name) / "submission.csv"
        submission.write_text("id,target\n1,0.5\n", encoding="utf-8")
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        calls = Path(self.tmp.name) / "uvx-calls.jsonl"
        fake_uvx = bin_dir / "uvx"
        fake_uvx.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
args = sys.argv[1:]
with open(os.environ["UVX_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
if "submissions" in args:
    print(json.dumps([
        {"ref": 999888, "fileName": "submission.csv", "description": "exp-key-1 candidate", "status": "SubmissionStatus.COMPLETE", "publicScore": ""}
    ]))
else:
    print("Successfully submitted to competition")
""",
            encoding="utf-8",
        )
        fake_uvx.chmod(0o755)

        submitted = self.run_cli(
            "submissions",
            "submit-file",
            "--competition-slug",
            "demo-comp",
            "--file",
            str(submission),
            "--message",
            "exp-key-1 candidate",
            "--experiment-key",
            "exp-key-1",
            "--json",
            env_overrides={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "UVX_CALLS": str(calls)},
        )
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        body = json.loads(submitted.stdout)
        self.assertEqual(body["submission"]["submission_ref"], "999888")

    def test_refresh_submissions_updates_scores_from_kaggle(self):
        self.run_cli(
            "submissions",
            "add",
            "--ref",
            "sub-1",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--json",
        )
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        calls = Path(self.tmp.name) / "uvx-calls.jsonl"
        fake_uvx = bin_dir / "uvx"
        fake_uvx.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["UVX_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps([{"ref": "sub-1", "fileName": "submission.csv", "status": "complete", "publicScore": "0.7"}]))
""",
            encoding="utf-8",
        )
        fake_uvx.chmod(0o755)

        refreshed = self.run_cli(
            "submissions",
            "refresh",
            "--competition-slug",
            "demo-comp",
            "--json",
            env_overrides={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "UVX_CALLS": str(calls)},
        )
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        rows = json.loads(refreshed.stdout)
        self.assertEqual(rows[0]["public_score"], 0.7)
        self.assertEqual(rows[0]["experiment_key"], "exp-key-1")
        call = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(
            call,
            ["kaggle", "competitions", "submissions", "demo-comp", "--format", "json", "--page-size", "200"],
        )

    def test_refresh_submissions_normalizes_enum_prefixed_status(self):
        # Found live: real Kaggle output is "SubmissionStatus.COMPLETE", not
        # "complete". The valid-status check didn't strip the prefix, so a real,
        # complete submission was recorded as valid: false.
        self.run_cli(
            "submissions",
            "add",
            "--ref",
            "sub-1",
            "--competition-slug",
            "demo-comp",
            "--json",
        )
        leaderboard = json.dumps(
            [{"ref": "sub-1", "fileName": "submission.csv", "status": "SubmissionStatus.COMPLETE", "publicScore": "0.7"}]
        )
        _, env_overrides = self.stub_uvx(leaderboard)
        refreshed = self.run_cli(
            "submissions", "refresh", "--competition-slug", "demo-comp", "--json", env_overrides=env_overrides
        )
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        rows = json.loads(refreshed.stdout)
        self.assertTrue(rows[0]["valid"])
        self.assertEqual(rows[0]["status"], "COMPLETE")

    def stub_uvx(self, output_json: str) -> tuple[Path, dict]:
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir(exist_ok=True)
        calls = Path(self.tmp.name) / "uvx-calls.jsonl"
        fake_uvx = bin_dir / "uvx"
        fake_uvx.write_text(
            f"""#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["UVX_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
print({output_json!r})
""",
            encoding="utf-8",
        )
        fake_uvx.chmod(0o755)
        return bin_dir, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "UVX_CALLS": str(calls)}

    def test_refresh_leaderboard_updates_matching_submission_rank(self):
        self.run_cli(
            "submissions",
            "add",
            "--ref",
            "sub-1",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--public-score",
            "0.7",
            "--json",
        )
        leaderboard = json.dumps(
            [
                {"teamName": "top-team", "score": "0.9"},
                {"teamName": "my-team", "score": "0.7"},
                {"teamName": "third-team", "score": "0.5"},
            ]
        )
        # Real `kaggle competitions leaderboard --show --format json` prints this
        # banner on stdout before the JSON array when more pages exist; verified
        # against the live API. Stubbing the clean-JSON case only would have hidden
        # the bug this shape triggers.
        stdout_with_pagination_banner = f"Next Page Token = CfDJ8EgiEKLz2SFK\n{leaderboard}"
        _, env_overrides = self.stub_uvx(stdout_with_pagination_banner)

        result = self.run_cli(
            "submissions",
            "refresh-leaderboard",
            "--competition-slug",
            "demo-comp",
            "--team-name",
            "my-team",
            "--json",
            env_overrides=env_overrides,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        self.assertTrue(body["ok"])
        self.assertEqual(body["rank"], 2)
        self.assertAlmostEqual(body["percentile"], 1 - (2 - 1) / 3)
        self.assertEqual(body["updated_submission"]["submission_ref"], "sub-1")
        self.assertEqual(body["updated_submission"]["rank"], 2)

        listed = self.run_cli("submissions", "list", "--json")
        rows = json.loads(listed.stdout)
        self.assertEqual(rows[0]["rank"], 2)
        self.assertAlmostEqual(rows[0]["percentile"], 1 - (2 - 1) / 3)

    def test_refresh_leaderboard_team_not_found_is_reported_not_crashed(self):
        leaderboard = json.dumps([{"teamName": "someone-else", "score": "0.9"}])
        _, env_overrides = self.stub_uvx(leaderboard)

        result = self.run_cli(
            "submissions",
            "refresh-leaderboard",
            "--competition-slug",
            "demo-comp",
            "--team-name",
            "my-team",
            "--json",
            env_overrides=env_overrides,
        )
        self.assertEqual(result.returncode, 1)
        body = json.loads(result.stdout)
        self.assertFalse(body["ok"])
        self.assertEqual(body["reason"], "team_not_found_in_fetched_page")

    def test_refresh_leaderboard_falls_back_to_profile_team_name(self):
        self.run_cli("profiles", "add", "demo-comp", "--team-name", "profile-team", "--json")
        self.run_cli(
            "submissions",
            "add",
            "--ref",
            "sub-1",
            "--competition-slug",
            "demo-comp",
            "--public-score",
            "0.7",
            "--json",
        )
        leaderboard = json.dumps([{"teamName": "profile-team", "score": "0.7"}])
        _, env_overrides = self.stub_uvx(leaderboard)

        result = self.run_cli(
            "submissions",
            "refresh-leaderboard",
            "--competition-slug",
            "demo-comp",
            "--json",
            env_overrides=env_overrides,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        self.assertTrue(body["ok"])
        self.assertEqual(body["rank"], 1)

    def test_refresh_leaderboard_without_team_name_anywhere_fails_clearly(self):
        result = self.run_cli(
            "submissions",
            "refresh-leaderboard",
            "--competition-slug",
            "no-profile-comp",
            "--json",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--team-name", result.stderr)

    def test_pull_output_from_directory_records_artifact_and_updates_run(self):
        output_dir = Path(self.tmp.name) / "kaggle-output"
        output_dir.mkdir()
        (output_dir / "submission.csv").write_text("id,target\n1,0.5\n", encoding="utf-8")
        (output_dir / "run.log").write_text("done\n", encoding="utf-8")

        self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "1",
            "--status",
            "COMPLETE",
        )

        pulled = self.run_cli("runs", "pull-output", "user/demo-kernel:v1", "--from-dir", str(output_dir), "--json")
        self.assertEqual(pulled.returncode, 0, pulled.stderr)
        artifact = json.loads(pulled.stdout)
        self.assertEqual(artifact["run_id"], "user/demo-kernel:v1")
        self.assertEqual(artifact["competition_slug"], "demo-comp")
        self.assertEqual(artifact["experiment_key"], "exp-key-1")
        self.assertEqual(artifact["kind"], "kaggle_output")
        self.assertEqual({row["name"] for row in artifact["files"]}, {"run.log", "submission.csv"})

        artifacts = json.loads((Path(self.tmp.name) / "artifacts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(artifacts), 1)
        runs = json.loads((Path(self.tmp.name) / "runs.json").read_text(encoding="utf-8"))
        self.assertTrue(runs[0]["outputs_pulled"])
        self.assertEqual(runs[0]["next_action"], "review_outputs")

    def test_review_output_marks_submission_candidate(self):
        output_dir = Path(self.tmp.name) / "kaggle-output"
        output_dir.mkdir()
        (output_dir / "submission.csv").write_text("id,target\n1,0.5\n", encoding="utf-8")
        self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "1",
            "--status",
            "COMPLETE",
        )
        self.run_cli("runs", "pull-output", "user/demo-kernel:v1", "--from-dir", str(output_dir), "--json")

        reviewed = self.run_cli("runs", "review-output", "user/demo-kernel:v1", "--json")
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        review = json.loads(reviewed.stdout)
        self.assertEqual(review["verdict"], "submission_candidate")
        self.assertEqual(review["next_action"], "human_review_submission")
        self.assertIn("submission_csv_present", review["passed_checks"])

        artifacts = json.loads((Path(self.tmp.name) / "artifacts.json").read_text(encoding="utf-8"))
        self.assertEqual(artifacts[0]["review"]["verdict"], "submission_candidate")
        runs = json.loads((Path(self.tmp.name) / "runs.json").read_text(encoding="utf-8"))
        self.assertEqual(runs[0]["next_action"], "human_review_submission")
        tasks = json.loads((Path(self.tmp.name) / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(tasks[0]["kind"], "human_review_submission")
        self.assertEqual(tasks[0]["status"], "open")

    def test_review_output_validates_submission_against_sample(self):
        output_dir = Path(self.tmp.name) / "kaggle-output"
        output_dir.mkdir()
        (output_dir / "submission.csv").write_text("id,target\n1,0.5\n2,0.7\n", encoding="utf-8")
        sample = Path(self.tmp.name) / "sample_submission.csv"
        sample.write_text("id,target\n1,0\n2,0\n", encoding="utf-8")
        self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "user/demo-kernel",
            "--version",
            "1",
            "--status",
            "COMPLETE",
        )
        self.run_cli("runs", "pull-output", "user/demo-kernel:v1", "--from-dir", str(output_dir), "--json")

        reviewed = self.run_cli(
            "runs",
            "review-output",
            "user/demo-kernel:v1",
            "--sample-submission",
            str(sample),
            "--json",
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        review = json.loads(reviewed.stdout)
        self.assertEqual(review["verdict"], "submission_candidate")
        self.assertIn("submission_columns_match_sample", review["passed_checks"])
        self.assertIn("submission_row_count_match_sample", review["passed_checks"])

    def test_metrics_recompute_rolls_up_observability(self):
        self.run_cli(
            "profiles",
            "add",
            "demo-comp",
            "--metric-direction",
            "minimize",
            "--json",
        )
        self.run_cli(
            "experiments",
            "add",
            "--competition-slug",
            "demo-comp",
            "--family",
            "gbdt-baseline",
            "--hypothesis",
            "baseline improves score",
            "--json",
        )
        self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--kernel-slug",
            "u/k",
            "--status",
            "ERROR",
            "--failure-class",
            "code",
        )
        self.run_cli(
            "submissions",
            "add",
            "--ref",
            "sub-1",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-1",
            "--public-score",
            "0.8",
            "--valid",
        )
        self.run_cli(
            "submissions",
            "add",
            "--ref",
            "sub-2",
            "--competition-slug",
            "demo-comp",
            "--experiment-key",
            "exp-key-2",
            "--public-score",
            "0.7",
            "--valid",
        )
        start = self.run_cli(
            "sessions",
            "start",
            "--harness",
            "codex",
            "--skill",
            "kaggle-next-experiment",
            "--competition-slug",
            "demo-comp",
            "--json",
        )
        session_id = json.loads(start.stdout)["session_id"]
        self.run_cli(
            "sessions",
            "end",
            session_id,
            "--outcome",
            "planned",
            "--tokens-input",
            "100",
            "--tokens-output",
            "25",
            "--json",
        )

        metrics = self.run_cli("metrics", "recompute", "--json")
        self.assertEqual(metrics.returncode, 0, metrics.stderr)
        body = json.loads(metrics.stdout)
        self.assertEqual(body["competitions"]["demo-comp"]["experiments"], 1)
        self.assertEqual(body["competitions"]["demo-comp"]["runs"], 1)
        self.assertEqual(body["competitions"]["demo-comp"]["failed_runs"], 1)
        self.assertEqual(body["competitions"]["demo-comp"]["best_public_score"], 0.7)
        self.assertEqual(
            [row["public_score"] for row in body["competitions"]["demo-comp"]["score_history"]],
            [0.8, 0.7],
        )
        self.assertEqual(body["competitions"]["demo-comp"]["score_history"][1]["experiment_key"], "exp-key-2")
        self.assertEqual(body["competitions"]["demo-comp"]["sessions"], 1)
        self.assertEqual(body["competitions"]["demo-comp"]["tokens"]["input"], 100)
        self.assertEqual(body["sessions"]["total_input_tokens"], 100)

    def test_metrics_recompute_computes_derived_health_metrics(self):
        self.run_cli("competitions", "add", "health-comp", "--decision", "joined", "--json")
        self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "health-comp",
            "--kernel-slug",
            "u/failed-run",
            "--status",
            "ERROR",
            "--failure-class",
            "code",
            "--json",
        )
        self.run_cli(
            "runs",
            "add",
            "--competition-slug",
            "health-comp",
            "--kernel-slug",
            "u/ok-run",
            "--status",
            "COMPLETE",
            "--json",
        )
        self.run_cli(
            "submissions",
            "add",
            "--ref",
            "health-sub-1",
            "--competition-slug",
            "health-comp",
            "--public-score",
            "0.5",
            "--percentile",
            "0.8",
            "--valid",
            "--json",
        )
        start = self.run_cli(
            "sessions",
            "start",
            "--harness",
            "claude",
            "--skill",
            "kaggle-next-experiment",
            "--competition-slug",
            "health-comp",
            "--json",
        )
        session_id = json.loads(start.stdout)["session_id"]
        self.run_cli(
            "sessions",
            "end",
            session_id,
            "--outcome",
            "planned",
            "--tokens-input",
            "10",
            "--tokens-output",
            "5",
            "--estimated-cost-usd",
            "1.0",
            "--json",
        )

        metrics = self.run_cli("metrics", "recompute", "--json")
        self.assertEqual(metrics.returncode, 0, metrics.stderr)
        data = json.loads(metrics.stdout)["competitions"]["health-comp"]
        self.assertEqual(data["failed_run_rate"], 0.5)
        self.assertEqual(data["cost_per_valid_submission"], 1.0)
        self.assertIsNotNone(data["days_to_first_valid_submission"])
        self.assertGreaterEqual(data["days_to_first_valid_submission"], 0.0)
        self.assertEqual(data["best_percentile"], 0.8)
        self.assertAlmostEqual(data["cost_per_percentile_point"], 1.0 / 80)

    def test_metrics_recompute_leaves_derived_metrics_null_without_data(self):
        self.run_cli(
            "experiments",
            "add",
            "--competition-slug",
            "empty-comp",
            "--family",
            "gbdt-baseline",
            "--hypothesis",
            "no runs yet",
            "--json",
        )
        metrics = self.run_cli("metrics", "recompute", "--json")
        data = json.loads(metrics.stdout)["competitions"]["empty-comp"]
        self.assertIsNone(data["failed_run_rate"])
        self.assertIsNone(data["cost_per_valid_submission"])
        self.assertIsNone(data["days_to_first_valid_submission"])
        self.assertIsNone(data["best_percentile"])
        self.assertIsNone(data["cost_per_percentile_point"])

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
            "--family",
            "feature-gbdt",
            "--what-changed",
            "Adds grouped fold feature interactions over baseline.",
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
        self.assertEqual(first_body["family"], "feature-gbdt")
        self.assertIn("what_changed", first_body)
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

    def test_experiment_family_repeat_requires_what_changed(self):
        first = self.run_cli(
            "experiments",
            "add",
            "--competition-slug",
            "demo-comp",
            "--family",
            "feature-gbdt",
            "--what-changed",
            "Initial feature-gbdt baseline.",
            "--hypothesis",
            "GBDT baseline gives a valid score",
            "--json",
        )
        self.assertEqual(first.returncode, 0, first.stderr)

        repeat = self.run_cli(
            "experiments",
            "add",
            "--competition-slug",
            "demo-comp",
            "--family",
            "feature-gbdt",
            "--hypothesis",
            "GBDT variant improves the baseline",
            "--json",
        )
        self.assertEqual(repeat.returncode, 1)
        self.assertIn("what_changed required", repeat.stderr)

        listing = self.run_cli("experiments", "list", "--competition-slug", "demo-comp", "--family", "feature-gbdt", "--json")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        rows = json.loads(listing.stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["family"], "feature-gbdt")

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

    def test_scout_competitions_applies_limit_per_group_not_globally(self):
        # Found via a live dogfood run: with the documented `--groups general
        # community --limit 20` and page_size 100, "general" alone can fill the
        # global limit before "community" is ever considered, silently dropping
        # it from output with no error or truncation signal.
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir(exist_ok=True)
        calls = Path(self.tmp.name) / "uvx-calls.jsonl"
        fake_uvx = bin_dir / "uvx"
        fake_uvx.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
args = sys.argv[1:]
with open(os.environ["UVX_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
group = args[args.index("--group") + 1]
rows = [
    {"ref": f"https://www.kaggle.com/competitions/{group}-comp-{i}", "deadline": "2030-01-01T00:00:00", "category": group}
    for i in range(5)
]
print(json.dumps(rows))
""",
            encoding="utf-8",
        )
        fake_uvx.chmod(0o755)

        proc = self.run_cli(
            "scout-competitions",
            "--groups",
            "general",
            "community",
            "--limit",
            "2",
            "--json",
            env_overrides={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "UVX_CALLS": str(calls)},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        groups_seen = {item["group"] for item in body["items"]}
        self.assertEqual(groups_seen, {"general", "community"})
        self.assertEqual(sum(1 for item in body["items"] if item["group"] == "general"), 2)
        self.assertEqual(sum(1 for item in body["items"] if item["group"] == "community"), 2)


if __name__ == "__main__":
    unittest.main()
