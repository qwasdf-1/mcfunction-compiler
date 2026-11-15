"""SCHED-COMP-020 correct distinct ScoreAdd instrumentation domains.

The 2026-11-15 failed attempt had fully valid real ore work but the test
falsely demanded one queue callback per queue advance and equality between
plain-text leaf wrappers and all typed scoreboard callbacks. These are
different counters by construction.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_scoreadd_workload_share as a

def record(name:str)->dict:
    return {
        "arm":name,
        "pinned_pack":a.EXPECTED_PACK_SHA,
        "native_state":{
            "player_mined_source_stat":1,
            "work_after":215,"work_expected":215,
            "run_state_after":0,"queue_head_delta":1952,
            "remaining_ore":0,"source_block_remains":0,
            "operation_markers_after":0,"target_markers_after":0,
        },
        "event_cpu":{"server_thread_cpu_running_ns":13_757_473_431},
        "queue_score_add_compiled":4 if name=="compiled_counter" else 0,
        "queue_score_add_executed_delta":7808 if name=="compiled_counter" else 0,
        "ray_score_add_executed_delta":1254 if name=="compiled_counter" else 0,
        "global_score_add_executed_delta":25939 if name=="compiled_counter" else 0,
        "typed_score_add_direct_successes_delta":10978 if name=="compiled_counter" else 0,
        "valid_scoreadd_path_coverage_diagnostic":name=="compiled_counter",
        "callback_metrics":None,
    }

def valid()->dict:
    result={item[0]:record(item[0]) for item in a.ARMS}
    # Values from failed 020's real command counters. New entry counters
    # are representative synthetic values: real run must independently
    # validate scoped<=all and direct-wrapper<=scoped.
    result["compiled_counter"]["callback_metrics"]={
        "optimized_score_add_leaf_callbacks":10353,
        "generic_leaf_callbacks":40533,
        "score_add_executed_counter_delta":25939,
        "total_ordinary_leaf_callbacks":50886,
        "typed_score_add_callback_entries":10978,
        "typed_score_add_callback_entries_in_scope":10978,
        "typed_score_add_direct_successes":10978,
        "specialized_counter_matches":False,
    }
    return result

class RealScoreAddReachTests(unittest.TestCase):
    def test_four_callbacks_per_head_step_not_one(self):
        report=a.interpret(valid())
        self.assertTrue(report["diagnostic_valid"])
        self.assertEqual(report["queue_scoreadd_compiled_commands"],4)
        self.assertEqual(report["queue_head_advances"],1952)
        self.assertEqual(report["queue_drain_scoreadd_executions"],4*1952)
        self.assertEqual(report["other_function_shared_family_counter_increments"],25939-7808-1254)

    def test_independent_counter_domains_not_falsely_equal(self):
        report=a.interpret(valid())
        self.assertEqual(report["actual_successful_typed_scoreadd_executions"],10978)
        self.assertEqual(report["aggregate_family_scoreadd_executed_increments"],25939)
        self.assertEqual(report["aggregate_family_increments_beyond_direct_scoreadd"],14961)
        self.assertEqual(report["directly_wrapped_optimized_leaf_callbacks"],10353)
        self.assertEqual(report["actual_typed_scoreadd_entries_outside_scope"],0)
        self.assertEqual(report["scoped_typed_entries_not_seen_as_direct_optimized_leaf"],625)
        self.assertAlmostEqual(
            report["scoreadd_fraction_of_observed_ordinary_leaf_callbacks"],10353/50886)
        self.assertIn("NOT the fraction",report["limitations_of_fraction"])
        self.assertIn("SHARED family counter",report["counter_domains"]["score_add_executed"])
        self.assertTrue(report["diagnostic_only"])

    def test_counter_domain_budget_not_observed_cpu(self):
        report=a.interpret(valid())
        self.assertAlmostEqual(
            report["required_15pct_whole_event_saving_ns_per_eligible_scoreadd"][
                "relative_to_off_cpu"],
            .15*13_757_473_431/10978)
        self.assertIn("NOT an observed command cost",report["required_saving_interpretation"])

    def test_queue_callback_mismatch_fails(self):
        records=valid()
        records["compiled_counter"]["queue_score_add_executed_delta"]=1952
        with self.assertRaises(AssertionError):a.interpret(records)
        records=valid()
        records["compiled_counter"]["queue_score_add_compiled"]=3
        with self.assertRaises(AssertionError):a.interpret(records)

    def test_callback_domain_ordering_fails_if_violated(self):
        for field,value in (
            ("typed_score_add_callback_entries",10000),
            ("typed_score_add_callback_entries_in_scope",10000),
            ("typed_score_add_direct_successes",11000),
            ("total_ordinary_leaf_callbacks",1),
        ):
            records=valid()
            records["compiled_counter"]["callback_metrics"][field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):
                a.interpret(records)

    def test_global_and_per_function_count_consistency(self):
        records=valid()
        records["compiled_counter"]["global_score_add_executed_delta"]=1
        with self.assertRaises(AssertionError):a.interpret(records)
        records=valid()
        records["compiled_counter"]["typed_score_add_direct_successes_delta"]=1
        with self.assertRaises(AssertionError):a.interpret(records)
        records=valid()
        records["compiled_counter"]["ray_score_add_executed_delta"]=0
        with self.assertRaises(AssertionError):a.interpret(records)

    def test_native_state_and_publisher_digest_are_hard_gates(self):
        records=valid()
        records["cached_cpu"]["native_state"]["remaining_ore"]=1
        with self.assertRaises(AssertionError):a.interpret(records)
        records=valid()
        records["compiled_counter"]["pinned_pack"]="unverified"
        with self.assertRaises(AssertionError):a.interpret(records)

    def test_unknown_arm_and_invalid_path_counter_fail(self):
        records=valid()
        del records["off_cpu"]
        with self.assertRaises(AssertionError):a.interpret(records)
        records=valid()
        records["compiled_counter"]["valid_scoreadd_path_coverage_diagnostic"]=False
        with self.assertRaises(AssertionError):a.interpret(records)

if __name__=="__main__":
    unittest.main()
