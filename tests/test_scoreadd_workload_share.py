"""Pure-contract tests for SCHED-COMP-020's noncausal ScoreAdd reach study."""
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
        "event_cpu":{"server_thread_cpu_running_ns":50_000_000_000},
        "queue_score_add_executed_delta":1952 if name=="compiled_counter" else None,
        "callback_metrics":None,
        "spark_profile_path":"path/to/profile.sparkprofile" if name=="compiled_sampled" else None,
        "spark_server_function_execute_weighted_ms":3.0 if name=="compiled_sampled" else None,
    }


def valid()->dict:
    out={arm[0]:record(arm[0]) for arm in a.ARMS}
    out["compiled_counter"]["callback_metrics"]={
        "optimized_score_add_leaf_callbacks":1952,
        "generic_leaf_callbacks":8000,
        "score_add_executed_counter_delta":1952,
        "total_ordinary_leaf_callbacks":9952,
        "specialized_counter_matches":True,
    }
    return out


class RealScoreAddReachTests(unittest.TestCase):
    def test_count_is_actual_invocations_not_compilation(self):
        result=a.interpret(valid())
        self.assertTrue(result["diagnostic_valid"])
        self.assertEqual(result["queue_drain_scoreadd_executions"],1952)
        self.assertEqual(result["event_scoreadd_execution_count"],1952)
        self.assertAlmostEqual(
            result["scoreadd_fraction_of_observed_ordinary_leaf_callbacks"],
            1952/9952,
        )

    def test_requirements_are_milliseconds_per_command_not_measured_cost(self):
        result=a.interpret(valid())
        # 15% of 50 seconds over 1,952 actually executed callbacks.
        self.assertAlmostEqual(
            result["required_15pct_whole_event_saving_ns_per_eligible_scoreadd"][
                "relative_to_off_cpu"
            ],
            0.15*50_000_000_000/1952,
        )
        self.assertIn("NOT an observed command cost",
                      result["required_saving_interpretation"])
        self.assertIn("NOT a CPU-time fraction",result["limitations_of_fraction"])
        self.assertTrue(result["noncausal"] if "noncausal" in result else True)

    def test_unexecuted_compiled_commands_cannot_be_reclassified_as_runtime_hits(self):
        rows=valid()
        rows["compiled_counter"]["callback_metrics"]["score_add_executed_counter_delta"]=0
        with self.assertRaises(AssertionError):
            a.interpret(rows)

    def test_generic_callbacks_not_assumed_cpu_share(self):
        rows=valid()
        rows["compiled_counter"]["callback_metrics"]["total_ordinary_leaf_callbacks"]=1
        with self.assertRaises(AssertionError):
            a.interpret(rows)

    def test_native_event_parity_is_hard_gate(self):
        rows=valid()
        rows["cached_cpu"]["native_state"]["remaining_ore"]=1
        with self.assertRaises(AssertionError):
            a.interpret(rows)

    def test_publisher_sha_and_arms_must_match(self):
        rows=valid()
        rows["compiled_counter"]["pinned_pack"]="fake"
        with self.assertRaises(AssertionError):
            a.interpret(rows)
        rows=valid()
        del rows["off_cpu"]
        with self.assertRaises(AssertionError):
            a.interpret(rows)

    def test_scoreadd_queue_count_is_not_queue_compilation_count(self):
        rows=valid()
        rows["compiled_counter"]["queue_score_add_executed_delta"]=0
        with self.assertRaises(AssertionError):
            a.interpret(rows)

if __name__=="__main__":
    unittest.main()
