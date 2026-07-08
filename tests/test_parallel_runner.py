import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

from kaggle_agent.parallel_runner import VariantSpec, resource_budget_from_percent, run_variants


class ResourceBudgetFromPercentTests(unittest.TestCase):
    def test_converts_percentages_to_concrete_limits_using_injected_specs(self):
        # 80% of 4 cores -> 3 concurrent (int truncation); 80% of 32000MB -> 25600MB.
        max_concurrent, max_rss = resource_budget_from_percent(
            cpu_percent=80, ram_percent=80, cpu_count=4, total_ram_mb_value=32000.0
        )
        self.assertEqual(max_concurrent, 3)
        self.assertEqual(max_rss, 25600.0)

    def test_never_returns_zero_concurrent_even_at_low_percent_or_single_core(self):
        max_concurrent, _ = resource_budget_from_percent(
            cpu_percent=5, ram_percent=50, cpu_count=1, total_ram_mb_value=1000.0
        )
        self.assertEqual(max_concurrent, 1)

    def test_rejects_out_of_range_percentages(self):
        with self.assertRaises(ValueError):
            resource_budget_from_percent(cpu_percent=0, ram_percent=80, cpu_count=4, total_ram_mb_value=1000.0)
        with self.assertRaises(ValueError):
            resource_budget_from_percent(cpu_percent=80, ram_percent=101, cpu_count=4, total_ram_mb_value=1000.0)

    def test_detects_real_machine_specs_when_not_injected(self):
        # No injected values: must read the real machine (matches how
        # kaggle-api-capabilities' probe measured 4 cores / ~32.9GB on Kaggle).
        max_concurrent, max_rss = resource_budget_from_percent(cpu_percent=100, ram_percent=100)
        self.assertGreaterEqual(max_concurrent, 1)
        self.assertGreater(max_rss, 0.0)


class RunVariantsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def sleepy_command(self, seconds: float) -> list[str]:
        return [sys.executable, "-c", f"import time; time.sleep({seconds})"]

    def timestamped_command(self, events_path: Path, name: str, seconds: float) -> list[str]:
        script = (
            "import json, time\n"
            f"with open({str(events_path)!r}, 'a') as f:\n"
            f"    f.write(json.dumps({{'name': {name!r}, 'event': 'start', 'time': time.time()}}) + '\\n')\n"
            f"time.sleep({seconds})\n"
            f"with open({str(events_path)!r}, 'a') as f:\n"
            f"    f.write(json.dumps({{'name': {name!r}, 'event': 'end', 'time': time.time()}}) + '\\n')\n"
        )
        return [sys.executable, "-c", script]

    def test_all_variants_run_and_results_collected(self):
        variants = [
            VariantSpec(name=f"v{i}", command=self.sleepy_command(0.05), log_path=self.root / f"v{i}.log")
            for i in range(3)
        ]
        results = run_variants(variants, max_concurrent=3)
        self.assertEqual({r.name for r in results}, {"v0", "v1", "v2"})
        self.assertTrue(all(r.returncode == 0 for r in results))
        self.assertTrue(all(r.log_path.exists() for r in results))

    def test_max_concurrent_is_never_exceeded(self):
        events_path = self.root / "events.jsonl"
        variants = [
            VariantSpec(
                name=f"v{i}",
                command=self.timestamped_command(events_path, f"v{i}", 0.3),
                log_path=self.root / f"v{i}.log",
            )
            for i in range(5)
        ]
        run_variants(variants, max_concurrent=2, poll_interval=0.02)

        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        # Reconstruct concurrency over time: at every start event, count how many
        # variants had started but not yet ended.
        intervals = {}
        for e in events:
            intervals.setdefault(e["name"], {})[e["event"]] = e["time"]
        for e in events:
            if e["event"] != "start":
                continue
            concurrent = sum(
                1
                for name, times in intervals.items()
                if times.get("start", float("inf")) <= e["time"] < times.get("end", float("inf"))
            )
            self.assertLessEqual(concurrent, 2, f"exceeded max_concurrent at {e}")

    def test_one_variant_failing_does_not_stop_others(self):
        variants = [
            VariantSpec(name="ok1", command=self.sleepy_command(0.02), log_path=self.root / "ok1.log"),
            VariantSpec(
                name="fails",
                command=[sys.executable, "-c", "import sys; sys.exit(1)"],
                log_path=self.root / "fails.log",
            ),
            VariantSpec(name="ok2", command=self.sleepy_command(0.02), log_path=self.root / "ok2.log"),
        ]
        results = run_variants(variants, max_concurrent=3)
        by_name = {r.name: r for r in results}
        self.assertEqual(by_name["ok1"].returncode, 0)
        self.assertEqual(by_name["ok2"].returncode, 0)
        self.assertEqual(by_name["fails"].returncode, 1)

    def test_resource_ceiling_holds_back_launches(self):
        # The ceiling check is necessarily reactive, not predictive: a variant's
        # real RSS can't be known before it starts, so run_variants only checks
        # *currently running* processes' RSS before launching another. Make
        # that unambiguous: one running process alone (200MB) already exceeds
        # the 150MB ceiling, so a second must never be launched concurrently.
        def fake_rss(pid: int) -> float:
            return 200.0

        events_path = self.root / "events.jsonl"
        variants = [
            VariantSpec(
                name=f"v{i}",
                command=self.timestamped_command(events_path, f"v{i}", 0.15),
                log_path=self.root / f"v{i}.log",
            )
            for i in range(3)
        ]
        run_variants(variants, max_concurrent=3, max_total_rss_mb=150.0, poll_interval=0.02, rss_reader=fake_rss)

        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        intervals = {}
        for e in events:
            intervals.setdefault(e["name"], {})[e["event"]] = e["time"]
        for e in events:
            if e["event"] != "start":
                continue
            concurrent = sum(
                1
                for name, times in intervals.items()
                if times.get("start", float("inf")) <= e["time"] < times.get("end", float("inf"))
            )
            self.assertLessEqual(concurrent, 1, f"resource ceiling should limit to 1 concurrent, got {concurrent} at {e}")

    def test_ceiling_never_fully_blocks_the_first_launch(self):
        # An unrealistically low ceiling must not deadlock the whole batch —
        # always allow at least one running process.
        variants = [VariantSpec(name="v0", command=self.sleepy_command(0.02), log_path=self.root / "v0.log")]
        results = run_variants(variants, max_concurrent=1, max_total_rss_mb=0.001, rss_reader=lambda pid: 999999.0)
        self.assertEqual(results[0].returncode, 0)


if __name__ == "__main__":
    unittest.main()
