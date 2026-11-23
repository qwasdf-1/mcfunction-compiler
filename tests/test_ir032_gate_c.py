"""Gate C regression contracts: never confuse diagnostic counts, CPU, or JFR."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_dynamic_lights_profile import parse_game_time_query
from ci_ir032_gate_c import (
    GROUPS, RUNS, check_result, compute_cpu_screen,
    normalize_frame, summarize_jfr,
)


def clean_case(scenario="stationary", jfr=False):
    population = {
        "item_entities": 24, "holder_entities": 4,
        "holder_entities_by_type": {
            "players": 4, "zombies": 0, "husks": 0,
            "foxes": 0, "zombie_villagers": 0, "allays": 0,
        },
        "other_light_sources": {
            "on_fire": 0, "tnt": 0, "glowing": 0,
            "glow_squids": 0, "allays": 0, "enchanted_armor": 0,
        },
    }
    rules = lambda name: {"rule": name, "query_response": f"{name} is set to false"}
    from ci_ir032_gate_c import PUBLISHER_PIN, PATCHED_PIN
    return {
        "datapack_sha256": PUBLISHER_PIN,
        "runtime_pack_sha256": PATCHED_PIN,
        "runtime_pack_is_publisher_byte_exact": False,
        "stack": "fabric", "function_compiler_wrapper": "on",
        "mode": "idle", "profile_seconds": 18,
        "scenario": f"24 tagged {scenario} dropped torches",
        "item_motion": {"scenario": scenario},
        "gate_c_cpu_capture_enabled": True,
        "gate_c_jfr_capture_enabled": jfr,
        "gate_c_jfr_execution_sample_period_ms": 2 if jfr else None,
        "compiler_exec_census_enabled": False,
        "spark": None, "spark_sampling": None,
        "mob_spawning_gamerule_status": rules("minecraft:spawn_mobs"),
        "daylight_gamerule_status": rules("minecraft:advance_time"),
        "source_population_before_profile": copy.deepcopy(population),
        "source_population_after_profile": copy.deepcopy(population),
        "tracked_items_before_profile": 24,
        "tracked_items_after_profile": 24,
        "tagged_torch_sources_before_profile": 24,
        "tagged_torch_sources_after_profile": 24,
        "pre_window_host_stability": {"stable": True},
        "game_ticks_during_window": 360,
        "server_thread_cpu": {
            "cpu_measurement_valid": True, "host_quality_pass": True,
            "cgroup_nr_throttled_delta": 0,
            "server_thread_cpu_running_ns": 360_000_000,
            "server_thread_cpu_ns_per_game_tick": 1_000_000,
            "server_thread_runqueue_wait_fraction": 0.01,
            "server_thread_pid": 212, "server_thread_tid": 232,
            "game_ticks_during_window": 360,
        },
        "jfr_path": "test.jfr" if jfr else None,
        "jfr_sha256": "fake-sha" if jfr else None,
    }


class IR032GateCTests(unittest.TestCase):
    def test_game_time_parser_accepts_one_integer_and_rejects_ambiguity(self):
        self.assertEqual(parse_game_time_query("The time is 360"), 360)
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            parse_game_time_query("error 20: time is 360")
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            parse_game_time_query("No time available")

    def test_cpu_run_accepted_without_spark_or_jfr(self):
        record = check_result(clean_case(), "stationary", False)
        self.assertEqual(record["cpu_ns_per_tick"], 1_000_000)
        self.assertEqual(record["game_ticks"], 360)

    def test_rejects_unpatched_original_or_mislabelled_patch(self):
        for name, value in [
            ("runtime_pack_sha256", "wrong"),
            ("runtime_pack_is_publisher_byte_exact", True),
        ]:
            case = clean_case()
            case[name] = value
            with self.assertRaisesRegex(AssertionError, "patch drift"):
                check_result(case, "stationary", False)

    def test_rejects_census_spark_jfr_and_host_drift(self):
        for name, value in [
            ("compiler_exec_census_enabled", True),
            ("spark", "1.10.194"),
            ("spark_sampling", {"cpu_interval_ms": 4}),
        ]:
            case = clean_case()
            case[name] = value
            with self.assertRaisesRegex(AssertionError, "contaminated"):
                check_result(case, "stationary", False)
        case = clean_case()
        case["server_thread_cpu"]["cgroup_nr_throttled_delta"] = 1
        with self.assertRaisesRegex(AssertionError, "Invalid Server-thread CPU"):
            check_result(case, "stationary", False)

    def test_cpu_jfr_modes_cannot_be_swapped(self):
        with self.assertRaisesRegex(AssertionError, "capture modes"):
            check_result(clean_case(jfr=True), "stationary", False)
        self.assertTrue(check_result(clean_case(jfr=True), "stationary", True)["jfr"])

    def test_rejects_low_frequency_jfr_and_jfr_settings_in_cpu_arm(self):
        case = clean_case(jfr=True)
        case["gate_c_jfr_execution_sample_period_ms"] = None
        with self.assertRaisesRegex(AssertionError, "2ms sampling"):
            check_result(case, "stationary", True)
        cpu = clean_case()
        cpu["gate_c_jfr_execution_sample_period_ms"] = 2
        with self.assertRaisesRegex(AssertionError, "JFR setting"):
            check_result(cpu, "stationary", False)

    def test_cpu_screen_is_descriptive_and_reports_noise(self):
        def row(label, scenario, cpu):
            return {"label": label, "scenario": scenario,
                    "jfr": False, "cpu_ns_per_tick": cpu}
        stable = [row("S1", "stationary", 10_000_000),
                  row("M1", "moving", 12_000_000),
                  row("M2", "moving", 12_100_000),
                  row("S2", "stationary", 10_100_000)]
        result = compute_cpu_screen(stable)
        self.assertTrue(result["noise_screen_pass"])
        self.assertGreater(result["moving_minus_stationary_fraction"], 0)
        self.assertTrue(result["not_a_15_percent_promotion_test"])
        stable[-1]["cpu_ns_per_tick"] = 14_000_000
        self.assertFalse(compute_cpu_screen(stable)["noise_screen_pass"])

    def test_jfr_slash_normalization_and_inclusive_overlap(self):
        frame = {"method": {"type": {"name": "net/minecraft/server/commands/FillCommand"},
                            "name": "fillBlocks"}}
        self.assertEqual(normalize_frame(frame)[0],
                         "net.minecraft.server.commands.FillCommand")
        self.assertTrue(GROUPS["block_and_fill"](*normalize_frame(frame)))
        example = {
            "type": "jdk.ExecutionSample",
            "values": {
                "sampledThread": {"osThreadId": 232},
                "state": "STATE_RUNNABLE",
                "stackTrace": {"frames": [
                    frame,
                    {"method": {"type": {"name": "net.minecraft.commands.execution.ExecutionContext"},
                                "name": "runCommandQueue"}},
                ]},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            recording = Path(tmp) / "test.jfr"
            recording.write_bytes(b"fake-jfr")
            response = type("Result", (), {
                "returncode": 0,
                "stdout": json.dumps({"recording": {"events": [example]}}),
                "stderr": "",
            })
            with patch("ci_ir032_gate_c.subprocess.run", return_value=response):
                summary = summarize_jfr(recording, 232)
        self.assertEqual(summary["runnable_server_thread_samples"], 1)
        self.assertEqual(summary["inclusive_sample_counts"]["block_and_fill"], 1)
        self.assertEqual(summary["inclusive_sample_counts"]["function_and_queue"], 1)
        self.assertTrue(summary["categories_overlap"])
        self.assertFalse(summary["coverage_sufficient"])


if __name__ == "__main__":
    unittest.main()
