"""Synthetic acceptance contracts for SCHED-ATTR-024 path census."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ci_scheduler_entry_census import analyze, EXPECTED_PACK_SHA

def native_data():
    return {
        "valid_native_workload":True, "valid_score_add_profile":True,
        "work_expected":215, "queue_head_delta":1952, "run_state_after":0,
        "tick_pre_event_stability":{"stable":True},
        "server_thread_event_cpu":{"cpu_measurement_valid":True,
            "host_quality_pass":True,"server_thread_cpu_running_ns":13_000_000_000},
        "datapack_sha256":EXPECTED_PACK_SHA,"compiler_mode":"score-add",
        "queue_score_add_compiled":4,"scheduler_path_census_enabled":True,
        "spark_capture_enabled":False,"jfr_cpu_capture_enabled":False,
        "command_callback_metrics_enabled":False,
        "selective_macro_arguments_metrics_enabled":False,
        "scheduler_path_census":{
            "session_count":1,"owner_java_thread_id":123,
            "queue_entries":100_000,"build_contexts":30_000,
            "execute_command":45_000,"call_function":25_000,"continuation":20_000,
        },
    }

class CensusContractTests(unittest.TestCase):
    def test_counts_are_not_cpu_or_disjoint_percentages(self):
        row=analyze(native_data())
        self.assertTrue(row["valid_census"])
        self.assertFalse(row["named_calls_are_disjoint"])
        self.assertIsNone(row["cpu_by_task_method_ns"])
        self.assertEqual(row["task_calls_per_dequeued_entry"]["call_function"],0.25)
        self.assertGreater(row["named_task_call_sum"],row["queue_entries"])

    def test_valid_zero_function_calls_are_not_imputed(self):
        d=native_data()
        d["scheduler_path_census"]["call_function"]=0
        row=analyze(d)
        self.assertEqual(row["task_method_entries"]["call_function"],0)

    def test_missing_observed_context_leaf_hook_rejected(self):
        d=native_data()
        d["scheduler_path_census"]["build_contexts"]=0
        with self.assertRaises(AssertionError): analyze(d)

    def test_wrong_publisher_ore_count_or_host_rejected(self):
        for field,value in (("datapack_sha256","bad"),("queue_head_delta",1951)):
            d=native_data()
            d[field]=value
            with self.assertRaises(AssertionError): analyze(d)
        d=native_data()
        d["server_thread_event_cpu"]["host_quality_pass"]=False
        with self.assertRaises(AssertionError): analyze(d)

    def test_no_census_or_wrong_session_rejected(self):
        d=native_data()
        d["scheduler_path_census"]["session_count"]=2
        with self.assertRaises(AssertionError): analyze(d)

    def test_negative_count_rejected(self):
        d=native_data()
        d["scheduler_path_census"]["continuation"]=-1
        with self.assertRaises(AssertionError): analyze(d)

if __name__=="__main__":
    unittest.main()
