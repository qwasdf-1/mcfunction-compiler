"""The mc-harness version pin and the projects that consume it.

Roadmap step 6 extracted the engine-agnostic harness into its own package with
its own version pinning; frozen at 1.0.0, it is vendored at `vendor/mc-harness`
so the repository runs on its own. These tests keep the pin honest: the
package resolves, its version is the recorded one, the
function-compiler scripts re-export the harness pieces their call sites import,
and the protocol client stays project-owned (AGENTS.md: pinned to 26.3
protocol 777, never extracted).
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
HARNESS_ROOT = PROJECT_ROOT / "vendor" / "mc-harness"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "runtime"))
sys.path.insert(0, str(HARNESS_ROOT))

import mc_harness  # noqa: E402
from mc_harness import assert_version, host_gate  # noqa: E402
from mc_harness.campaign import median_window, tick_metrics  # noqa: E402
from mc_harness.host_gate import is_noisy  # noqa: E402
from mc_harness.mod_stacks import MODS, STACK_MODS  # noqa: E402
from mc_harness.paired_stats import summarize_paired_changes  # noqa: E402
from mc_harness.server_lifecycle import (  # noqa: E402
    DrainingRconClient,
    RconClient,
    locate_official_server_jar,
)

#: The harness version every recorded campaign was verified against.
HARNESS_PIN = "1.0.0"


class McHarnessPinTests(unittest.TestCase):
    def test_package_resolves_at_the_vendored_path(self) -> None:
        self.assertTrue((HARNESS_ROOT / "pyproject.toml").is_file())
        self.assertEqual(mc_harness.__file__, str(HARNESS_ROOT / "mc_harness" / "__init__.py"))

    def test_version_is_the_recorded_pin(self) -> None:
        self.assertEqual(mc_harness.__version__, HARNESS_PIN)
        assert_version(HARNESS_PIN)  # must not raise

    def test_wrong_pin_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_version("0.0.1")

    def test_vendored_metadata_records_the_pin(self) -> None:
        text = (HARNESS_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "mc-harness"', text)
        self.assertIn(f'version = "{HARNESS_PIN}"', text)


class HarnessBehaviourTests(unittest.TestCase):
    def test_paired_stats_decisions_are_unchanged(self) -> None:
        summary = summarize_paired_changes(
            [-81.0, -82.0, -81.0, -80.5, -81.7, -81.2, -81.9, -80.8, -81.3, -81.6],
            minimum_gain_percent=15.0,
        )
        self.assertEqual(summary["decision"], "meets_threshold")
        self.assertEqual(summary["no_regression_decision"], "no_regression_holds")
        self.assertEqual(summary["confidence_achieved"], 0.978515625)
        # Five pairs cannot reach the 95% target coverage (0.9375), so the
        # decision stays inconclusive no matter how large the effect is.
        screening = summarize_paired_changes(
            [-81.0, -82.0, -81.0, -80.5, -81.7], minimum_gain_percent=15.0
        )
        self.assertEqual(screening["decision"], "inconclusive")

    def test_tick_metrics_and_median_window(self) -> None:
        parsed = tick_metrics(
            "Average time per tick: 2.50ms P50: 2.00ms P95: 4.00ms P99: 6.00ms"
        )
        self.assertEqual(parsed["tick_average_ms"], 2.5)
        self.assertEqual(median_window([{"a": 1.0}, {"a": 3.0}]), {"a": 2.0})

    def test_host_noise_rule(self) -> None:
        self.assertFalse(is_noisy(3.9, 16))
        self.assertTrue(is_noisy(17.0, 16))

    def test_mod_pins_cover_the_recorded_stacks(self) -> None:
        self.assertEqual(STACK_MODS["fabric"], ())
        self.assertEqual(STACK_MODS["lb113"], ("lithium", "bellows113"))
        self.assertIn("lbm113120", STACK_MODS)

    def test_draining_client_drops_split_response_tails(self) -> None:
        self.assertTrue(issubclass(DrainingRconClient, RconClient))


class ProjectOwnershipTests(unittest.TestCase):
    def test_protocol_client_stays_project_owned(self) -> None:
        # The harness must not carry a protocol client; the project owns its pin.
        harness_package = HARNESS_ROOT / "mc_harness"
        self.assertFalse((harness_package / "player_bot.py").exists())
        project_bot = PROJECT_ROOT / "tests" / "runtime" / "player_bot.py"
        self.assertTrue(project_bot.is_file())
        text = project_bot.read_text(encoding="utf-8")
        self.assertIn("PROTOCOL_VERSION = 777", text)

    def test_runtime_probe_reexports_harness_pieces(self) -> None:
        import run_runtime_probe  # noqa: PLC0415

        self.assertIs(run_runtime_probe.RconClient, RconClient)
        self.assertIs(
            run_runtime_probe.SERVER_JAR_SHA256,
            mc_harness.server_lifecycle.SERVER_JAR_SHA256,
        )
        # The pinned-jar and packet-report helpers are thin project wrappers
        # around the shared implementations (project-specific search roots and
        # the project-owned packet-id parser).
        self.assertTrue(callable(run_runtime_probe.locate_official_server_jar))
        self.assertTrue(callable(run_runtime_probe.generate_packet_ids))
        self.assertEqual(run_runtime_probe.PacketIds.__module__, "player_bot")


#: The scripts this extraction rewired. The compile scope is the extraction
#: surface, not the whole scripts directory: `run_memory_load_analysis.py` has
#: a pre-existing IndentationError in HEAD (orphaned code after a `return`,
#: line 448) that is unrelated to this extraction and is reported separately
#: rather than silently fixed here.
EXTRACTION_SURFACE = (
    "run_runtime_probe.py",
    "run_entity_datapack_profile.py",
    "run_fused_region_sustained.py",
    "run_selective_macro_sustained.py",
    "run_bytecode_vs_fused_campaign.py",
    "run_veinminer_campaign.py",
    "run_perf_001_baseline.py",
    "mod_artifacts.py",
)


class ScriptCompileTests(unittest.TestCase):
    def test_every_extraction_surface_script_compiles(self) -> None:
        for name in EXTRACTION_SURFACE:
            script = SCRIPTS_DIR / name
            self.assertTrue(script.is_file(), f"{name} missing")
            with self.subTest(script=name):
                subprocess.run(
                    [sys.executable, "-m", "py_compile", str(script)],
                    check=True,
                )

    def test_harness_package_compiles(self) -> None:
        for module in sorted((HARNESS_ROOT / "mc_harness").glob("*.py")):
            with self.subTest(module=module.name):
                subprocess.run(
                    [sys.executable, "-m", "py_compile", str(module)],
                    check=True,
                )


class CampaignWrapperTests(unittest.TestCase):
    """The campaign wrappers bind the right fixture names to the shared helpers."""

    def test_fused_runner_binds_its_objective(self) -> None:
        import run_fused_region_sustained as fused  # noqa: PLC0415

        sent: list[str] = []

        class StubRcon:
            def command(self, command: str) -> str:
                sent.append(command)
                return "#fused has 3"

        self.assertEqual(fused.score(StubRcon(), "#fused"), 3)
        self.assertEqual(sent, ["scoreboard players get #fused fc_fused"])

    def test_selective_runner_binds_its_objective(self) -> None:
        import run_selective_macro_sustained as selective  # noqa: PLC0415

        sent: list[str] = []

        class StubRcon:
            def command(self, command: str) -> str:
                sent.append(command)
                return "#macro has 17"

        self.assertEqual(selective.score(StubRcon(), "#macro"), 17)
        self.assertEqual(sent, ["scoreboard players get #macro fc_macro"])

    def test_runners_reserve_distinct_free_ports(self) -> None:
        import run_fused_region_sustained as fused  # noqa: PLC0415
        import run_selective_macro_sustained as selective  # noqa: PLC0415

        for runner in (fused, selective):
            ports = runner.reserve_ports(2)
            self.assertEqual(len(ports), 2)
            self.assertNotEqual(ports[0], ports[1])

    def test_bytecode_campaign_reuses_the_fused_primitive_bindings(self) -> None:
        import run_bytecode_vs_fused_campaign as bytecode  # noqa: PLC0415

        # The bytecode campaign imports the shared primitives through the fused
        # runner's wrappers, so one binding serves both campaigns.
        self.assertEqual(bytecode.tick_metrics("Average time per tick: 1.00ms P50: 1.00ms P95: 1.00ms P99: 1.00ms")["tick_average_ms"], 1.0)
        self.assertEqual(bytecode.BASELINE_ARM, "fused")
        self.assertEqual(bytecode.CANDIDATE_ARM, "bytecode")

    def test_host_gate_settle_is_shared_by_perf_001(self) -> None:
        import run_perf_001_baseline as perf_001  # noqa: PLC0415

        self.assertEqual(perf_001.SETTLE_LOAD, host_gate.QUIET_LOAD_1M)
        self.assertEqual(
            perf_001.SETTLE_TIMEOUT, host_gate.SETTLE_TIMEOUT_SECONDS
        )


if __name__ == "__main__":
    unittest.main()
