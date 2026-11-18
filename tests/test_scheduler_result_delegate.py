"""Synthetic SCHED-ATTR-028 delegate classification and raw CPU conservation."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ci_scheduler_result_delegate import interpret,ARMS
from test_scheduler_plumbing_cpu import records as parent_records


def records():
    rows=parent_records()
    for arm,mode in ARMS:
        active=mode!="off"
        timed=mode=="timed"
        rows[arm]["delegate_trace"]={
            "mode":mode,
            "calls":800 if active else 0,
            "timed_samples":800 if timed else 0,
            "raw_cpu_ns":2_000_000 if timed else 0,
            "success":798 if active else 0,
            "failure":2 if active else 0,
            "non_execution_source":0,
            "groups":([] if not active else [
                {
                    "type":"EMPTY",
                    "calls":200,
                    "raw_cpu_ns":200_000 if timed else 0,
                    "timed_samples":200 if timed else 0,
                    "success":199,"failure":1,
                },
                {
                    "type":"net.minecraft.commands.CommandResultCallback$$Lambda",
                    "calls":600,
                    "raw_cpu_ns":1_800_000 if timed else 0,
                    "timed_samples":600 if timed else 0,
                    "success":599,"failure":1,
                },
            ]),
        }
    return rows


class DelegateBreakdownTests(unittest.TestCase):
    def test_root_adapter_is_not_misidentified_as_underlying_delegate(self):
        r=interpret(records())
        self.assertTrue(r["diagnostic_valid"])
        self.assertEqual(r["observed_selected_callbacks"],800)
        groups=r["callback_types_sorted_by_observed_cpu"]
        self.assertEqual(groups[0]["delegate_owner_class"],
                         "net.minecraft.commands.CommandResultCallback$$Lambda")
        self.assertEqual(groups[0]["sampled_raw_cpu_fraction_of_all_callbacks"],0.9)
        self.assertIn("chain",groups[0]["classification_limit"])
        self.assertEqual(groups[1]["delegate_owner_class"],"EMPTY")
        self.assertIn("not exact exclusive",r["limitations"])

    def test_class_census_is_sorted_by_timed_cpu_not_call_count(self):
        d=records()
        g=d["timed_tasks"]["delegate_trace"]["groups"]
        g[0]["raw_cpu_ns"]=1_900_000
        g[1]["raw_cpu_ns"]=100_000
        r=interpret(d)
        self.assertEqual(r["callback_types_sorted_by_observed_cpu"][0]["delegate_owner_class"],"EMPTY")

    def test_rare_delegate_not_presented_as_powered(self):
        d=records()
        for arm in ("timed_tasks","empty_control"):
            g=d[arm]["delegate_trace"]["groups"]
            g[0]["calls"]=4
            g[0]["timed_samples"]=4 if arm=="timed_tasks" else 0
            g[0]["success"]=3
            g[0]["failure"]=1
            g[1]["calls"]=796
            g[1]["timed_samples"]=796 if arm=="timed_tasks" else 0
            g[1]["success"]=795
            g[1]["failure"]=1
        r=interpret(d)
        rare=[g for g in r["callback_types_sorted_by_observed_cpu"]
              if g["delegate_owner_class"]=="EMPTY"][0]
        self.assertFalse(rare["adequately_exposed_for_descriptive_group_screen"])

    def test_overflow_capacity_more_than_five_percent_fails(self):
        d=records()
        for arm in ("timed_tasks","empty_control"):
            g=d[arm]["delegate_trace"]["groups"]
            g[0]["type"]="OTHER"
            g[0]["calls"]=200
        with self.assertRaises(AssertionError): interpret(d)

    def test_group_missing_in_control_is_labelled_underpowered(self):
        d=records()
        # We do not manufacture a matched control group when a class occurs
        # only in timed. Keep the label and mark its precision as unsupported.
        g=d["empty_control"]["delegate_trace"]["groups"]
        g[0]["type"]="dev.functioncompiler.OnlyInEmpty"
        a=interpret(d)
        chain=a["callback_types_sorted_by_observed_cpu"][0]
        self.assertTrue(chain["adequately_exposed_for_descriptive_group_screen"])
        empty=[x for x in a["callback_types_sorted_by_observed_cpu"]
               if x["delegate_owner_class"]=="EMPTY"][0]
        self.assertFalse(empty["adequately_exposed_for_descriptive_group_screen"])

    def test_wrong_native_event_is_rejected(self):
        d=records()
        d["timed_tasks"]["native_state"]["ore"]=214
        with self.assertRaises(AssertionError):interpret(d)

if __name__=="__main__":
    unittest.main()
