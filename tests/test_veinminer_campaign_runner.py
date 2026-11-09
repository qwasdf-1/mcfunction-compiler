"""Tests for the Vein Miner campaign runner's arm construction and gates.

The campaign's paired arms must stay uninstrumented: the selective-macro hit
counter perturbs timing, so activation is proven by a separate metrics-on
diagnostic. These tests pin that split without launching a server.
"""

from __future__ import annotations

import argparse
import unittest

from scripts.run_veinminer_campaign import (
    profile_command,
    selective_activation_summary,
)


def campaign_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "stack": "fabric",
        "side": 6,
        "capture_timeout": 60,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class ProfileCommandTests(unittest.TestCase):
    def test_selective_timing_arm_is_uninstrumented(self) -> None:
        command = profile_command(campaign_args(), "selective-macro")
        self.assertEqual(
            command[command.index("--compiler-mode") + 1], "selective-macro"
        )
        self.assertNotIn("--count-selective-macro-arguments", command)

    def test_off_timing_arm_is_uninstrumented(self) -> None:
        command = profile_command(campaign_args(), "off")
        self.assertEqual(command[command.index("--compiler-mode") + 1], "off")
        self.assertNotIn("--count-selective-macro-arguments", command)

    def test_fused_timing_arm_uses_the_uninstrumented_mode(self) -> None:
        command = profile_command(campaign_args(), "fused")
        self.assertEqual(
            command[command.index("--compiler-mode") + 1], "fused-timed"
        )
        self.assertNotIn("--count-selective-macro-arguments", command)

    def test_activation_diagnostic_enables_the_hit_counter(self) -> None:
        command = profile_command(
            campaign_args(),
            "selective-macro",
            count_selective_macro_arguments=True,
        )
        self.assertIn("--count-selective-macro-arguments", command)

    def test_hit_counter_is_rejected_on_other_arms(self) -> None:
        with self.assertRaises(ValueError):
            profile_command(
                campaign_args(),
                "off",
                count_selective_macro_arguments=True,
            )


def activation_result(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "valid_native_workload": True,
        "valid_selective_macro_profile": True,
        "selective_macro_argument_calls_delta": 11701,
        "selective_macro_diagnostics_delta": {
            "attempted": 11701,
            "unsupported_providers": 0,
            "unsupported_entity_paths": 0,
            "invalid_storage_sources": 0,
            "missing_entity_custom_data": 0,
            "macro_resolution_fallbacks": 0,
            "missing_selected_keys": 0,
        },
        "selective_macro_provider_class_delta": {},
        "selective_macro_arguments_metrics_enabled": True,
        "work_after": 215,
        "work_expected": 215,
        "queue_head_delta": 1952,
        "operation_completion_seconds": 1.5,
        "timing_instrumentation": "no Spark; selective-macro hit counter enabled",
    }
    values.update(overrides)
    return values


class SelectiveActivationTests(unittest.TestCase):
    def test_summary_records_calls_and_counters(self) -> None:
        summary = selective_activation_summary(
            {"output": "/tmp/run-1"},
            activation_result(),
        )
        self.assertEqual(summary["run_id"], "run-1")
        self.assertEqual(summary["selective_macro_argument_calls_delta"], 11701)
        self.assertEqual(
            summary["selective_macro_diagnostics_delta"]["attempted"], 11701
        )
        self.assertTrue(summary["valid_activation"])

    def test_native_workload_failure_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            selective_activation_summary(
                {"output": "/tmp/run"},
                activation_result(valid_native_workload=False),
            )

    def test_profile_gate_failure_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            selective_activation_summary(
                {"output": "/tmp/run"},
                activation_result(valid_selective_macro_profile=False),
            )

    def test_zero_calls_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            selective_activation_summary(
                {"output": "/tmp/run"},
                activation_result(selective_macro_argument_calls_delta=0),
            )

    def test_zero_attempts_is_rejected(self) -> None:
        diagnostics = dict(
            activation_result()["selective_macro_diagnostics_delta"]
        )
        diagnostics["attempted"] = 0
        with self.assertRaises(ValueError):
            selective_activation_summary(
                {"output": "/tmp/run"},
                activation_result(selective_macro_diagnostics_delta=diagnostics),
            )


if __name__ == "__main__":
    unittest.main()
