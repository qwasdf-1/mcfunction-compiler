"""IR-030 original-gameplay verification rejects incomplete coverage and drift."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir030_native_event import PIN, verify_event


def status(*, after: bool = False) -> str:
    flags = {
        "ir030_pos_get_enabled": "true",
        "ir030_pos_get_verify": "true",
        "score_add_prototype_enabled": "false",
        "score_add_metrics_enabled": "false",
        "score_add_timing_enabled": "false",
        "fused_region_prototype_enabled": "false",
        "bytecode_region_prototype_enabled": "false",
    }
    counters = {f"ir030_pos_compiled_{a}": 1 for a in "xyz"}
    counters.update({f"ir030_pos_fast_{a}": 1940 if after else 0 for a in "xyz"})
    counters.update({
        "ir030_pos_verified": 5820 if after else 0,
        "ir030_pos_verify_mismatches": 0,
        "ir030_pos_invalid_targets": 0,
        "ir030_pos_fallback_vehicle": 0,
        "ir030_pos_fallback_entity_type": 0,
        "ir030_pos_fallback_nonfinite": 0,
    })
    return " ".join(f"{k}={v}" for k, v in {**flags, **counters}.items())


def event() -> dict:
    return {
        "datapack_sha256": PIN,
        "compiler_mode": "wrapper",
        "stack": "fabric",
        "valid_native_workload": True,
        "work_after": 215,
        "queue_head_delta": 1952,
        "run_state_after": 0,
        "remaining_ore": 0,
        "source_block_remains": 0,
        "operation_markers_after": 0,
        "target_markers_after": 0,
        "event_timeout_reached": False,
        "tick_pre_event_stability": {"stable": True},
        "server_thread_event_cpu": {
            "host_quality_pass": True,
            "cpu_measurement_valid": True,
            "server_thread_cpu_running_ns": 123456789,
        },
        "command_callback_metrics_enabled": False,
        "compiler_exec_census_enabled": False,
        "compiler_acceptance_audit_enabled": False,
        "cpu005_mode": None,
        "jfr_cpu_capture_enabled": False,
        "jfr_execution_capture_enabled": False,
        "spark_capture_enabled": False,
        "compiler_status_before": status(after=False),
        "compiler_status_after": status(after=True),
    }


class OriginalEventIR030Tests(unittest.TestCase):
    def test_accepts_exact_authentic_source_exposure(self):
        outcome = verify_event(event())
        self.assertEqual(outcome["exact_fast_calls"], dict.fromkeys("xyz", 1940))
        self.assertEqual(outcome["native_snapshot_verifications"], 5820)

    def test_rejects_missing_coordinate_invocations(self):
        case = event()
        case["compiler_status_after"] = case["compiler_status_after"].replace(
            "ir030_pos_fast_z=1940", "ir030_pos_fast_z=1939")
        with self.assertRaisesRegex(AssertionError, "coverage drift"):
            verify_event(case)

    def test_rejects_changed_native_result(self):
        case = event()
        case["compiler_status_after"] = case["compiler_status_after"].replace(
            "ir030_pos_verify_mismatches=0", "ir030_pos_verify_mismatches=1")
        with self.assertRaisesRegex(AssertionError, "read mismatch"):
            verify_event(case)

    def test_rejects_unexpected_native_fallback(self):
        case = event()
        case["compiler_status_after"] = case["compiler_status_after"].replace(
            "ir030_pos_fallback_vehicle=0", "ir030_pos_fallback_vehicle=1")
        with self.assertRaisesRegex(AssertionError, "left exact Marker"):
            verify_event(case)

    def test_rejects_disabled_verifier(self):
        case = event()
        case["compiler_status_before"] = case["compiler_status_before"].replace(
            "ir030_pos_get_verify=true", "ir030_pos_get_verify=false")
        with self.assertRaisesRegex(AssertionError, "verification disabled"):
            verify_event(case)

    def test_rejects_drifted_world_conservation(self):
        case = event()
        case["queue_head_delta"] -= 1
        with self.assertRaisesRegex(AssertionError, "completion/parity"):
            verify_event(case)

    def test_rejects_mixed_profiler(self):
        case = event()
        case["jfr_cpu_capture_enabled"] = True
        with self.assertRaisesRegex(AssertionError, "profiling instrumentation"):
            verify_event(case)

    def test_rejects_unpinned_source(self):
        case = event()
        case["datapack_sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "publisher SHA"):
            verify_event(case)


if __name__ == "__main__":
    unittest.main()
