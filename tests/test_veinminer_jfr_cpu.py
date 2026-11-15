"""Synthetic contracts for SCHED-COMP-021; no Minecraft installation required."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_veinminer_jfr_cpu import (  # noqa: E402
    _category, interpret_events, MAX_INVALID_FRACTION,
)
from ci_scoreadd_cpu_attribution import ARMS, EXPECTED_PACK_SHA, interpret  # noqa: E402


def sample(*classes, tid=4242, failed=False, biased=False, type_name="jdk.CPUTimeSample"):
    frames = [
        {"method": {"type": {"name": clazz.replace(".", "/")}, "name": name}}
        for clazz, name in classes
    ]
    values = {
        "eventThread": {"javaName": "Server thread", "osThreadId": tid},
        "failed": failed, "biased": biased,
        "stackTrace": {"truncated": False, "frames": frames},
    }
    return {"type": type_name, "values": values}


SCORE_ADD = ("dev.functioncompiler.ScoreAddCommand", "runUntimed")
MODIFIER = ("dev.functioncompiler.ContextModifierCommand", "run")
SCHEDULER = ("net.minecraft.server.ServerFunctionManager", "execute")
QUEUE = ("net.minecraft.commands.execution.ExecutionContext", "runCommandQueue")
WORLD = ("net.minecraft.server.level.ServerLevel", "tick")


class JfrCpuAttributionTests(unittest.TestCase):
    def test_typed_scoreadd_wins_over_enclosing_modifier_and_scheduler(self):
        self.assertEqual(_category([SCORE_ADD, MODIFIER, SCHEDULER]), "typed-scoreadd")
        self.assertEqual(_category([MODIFIER, SCHEDULER]), "other-specialized")
        self.assertEqual(_category([SCHEDULER, QUEUE]), "function-queue-or-nested")
        self.assertEqual(_category([WORLD]), "world-updates")
        self.assertEqual(
            _category([("dev.functioncompiler.UnknownWrapper", "run"), SCHEDULER]),
            "other-compiler"
        )

    def test_compiler_callbacks_beat_dispatch_but_not_vanilla_fallbacks(self):
        unknown = ("dev.functioncompiler.InlinedFunctionCommand", "run")
        brigadier = ("com.mojang.brigadier.context.ContextChain", "executeAll")
        vanilla_score = ("net.minecraft.server.commands.ScoreboardCommand", "addScore")
        execute = ("net.minecraft.server.commands.ExecuteCommand", "lambda$run")
        self.assertEqual(_category([unknown, brigadier, QUEUE, SCHEDULER]), "other-compiler")
        self.assertEqual(_category([vanilla_score, unknown, QUEUE]), "vanilla-scoreboard")
        self.assertEqual(_category([execute, unknown, QUEUE]), "execute-control")
        self.assertEqual(_category([brigadier, QUEUE]), "function-queue-or-nested")
        self.assertEqual(_category([brigadier]), "brigadier-dispatch")

    def test_every_valid_sample_is_classified_exactly_once(self):
        events = ([sample(SCORE_ADD, MODIFIER, SCHEDULER)] * 80
                  + [sample(MODIFIER, SCHEDULER)] * 30
                  + [sample(SCHEDULER, QUEUE)] * 60
                  + [sample(WORLD)] * 30
                  + [sample(SCORE_ADD, tid=9999)] * 40)
        result = interpret_events(events, 4242)
        self.assertEqual(result["valid_server_cpu_samples"], 200)
        self.assertEqual(result["categories"]["typed-scoreadd"]["samples"], 80)
        self.assertEqual(result["categories"]["other-specialized"]["samples"], 30)
        self.assertAlmostEqual(result["scoreadd_sampled_cpu_fraction"], 0.4)
        self.assertEqual(sum(x["samples"] for x in result["categories"].values()), 200)
        self.assertEqual(result["all_threads_cpu_sample_events"], 240)

    def test_failed_samples_not_relabelled_as_other_work(self):
        events = [sample(SCORE_ADD)] * 200 + [sample(failed=True)] * 10
        result = interpret_events(events, 4242)
        self.assertEqual(result["valid_server_cpu_samples"], 200)
        self.assertEqual(result["failed_server_cpu_samples"], 10)
        self.assertEqual(result["categories"]["typed-scoreadd"]["samples"], 200)
        bad = [sample(SCORE_ADD)] * 200 + [sample(failed=True)] * 30
        self.assertGreater(30 / 230, MAX_INVALID_FRACTION)
        with self.assertRaises(ValueError):
            interpret_events(bad, 4242)

    def test_missing_cpu_sampler_or_too_few_server_samples_rejected(self):
        with self.assertRaises(ValueError):
            interpret_events([{"type": "jdk.ExecutionSample", "values": {}}], 4242)
        with self.assertRaises(ValueError):
            interpret_events([sample(SCORE_ADD)] * 149, 4242)

    def test_lost_cpu_time_samples_fail_coverage_gate(self):
        lost = {
            "type": "jdk.CPUTimeSamplesLost",
            "values": {"eventThread": {"javaName": "Server thread",
                                        "osThreadId": 4242},
                       "lostSamples": 30}
        }
        with self.assertRaises(ValueError):
            interpret_events([sample(SCORE_ADD)] * 200 + [lost], 4242)

    def test_thread_identity_and_bias_are_visible(self):
        r = interpret_events([sample(SCORE_ADD, biased=True)] * 200, 4242)
        self.assertEqual(r["biased_server_cpu_samples"], 200)
        self.assertTrue(r["diagnostic_valid"])
        with self.assertRaises(ValueError):
            interpret_events([sample(SCORE_ADD, tid=1111)] * 200, 4242)


def arm(name: str):
    return {
        "arm": name, "mode": dict(ARMS)[name],
        "pinned_pack": EXPECTED_PACK_SHA,
        "native_state": {"work_after": 215, "queue_head_delta": 1952},
        "server_thread_cpu_running_ns": 17_000_000_000,
        "server_thread_host_quality": True,
        "sample_attribution": {
            "diagnostic_valid": True,
            "scoreadd_sampled_cpu_fraction": .05,
            "scoreadd_ideal_elimination_upper_bound_from_samples": .05,
        },
    }


class CampaignContractTests(unittest.TestCase):
    def test_fresh_two_arm_diagnostic_does_not_claim_cpu_speedup(self):
        results = {n: arm(n) for n, _ in ARMS}
        out = interpret(results)
        self.assertTrue(out["diagnostic_only"])
        self.assertIn("not causal", out["interpretation"])
        self.assertEqual(out["cached_ideal_scoreadd_elimination_upper_bound_from_samples"], .05)

    def test_missing_arms_and_native_parity_fail(self):
        r = {n: arm(n) for n, _ in ARMS}
        with self.assertRaises(AssertionError):
            interpret({"off_jfr": r["off_jfr"]})
        r["cached_jfr"]["native_state"]["work_after"] = 214
        with self.assertRaises(AssertionError):
            interpret(r)

    def test_host_or_publisher_failure_rejected(self):
        r = {n: arm(n) for n, _ in ARMS}
        r["off_jfr"]["pinned_pack"] = "wrong"
        with self.assertRaises(AssertionError):
            interpret(r)
        r = {n: arm(n) for n, _ in ARMS}
        r["cached_jfr"]["server_thread_host_quality"] = False
        with self.assertRaises(AssertionError):
            interpret(r)


if __name__ == "__main__":
    unittest.main()
