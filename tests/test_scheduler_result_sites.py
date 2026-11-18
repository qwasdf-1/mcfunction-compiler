"""Strict synthetic site counts and no-causal interpretation for SCHED-ATTR-028-D."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ci_scheduler_result_sites import interpret


def fixture():
    delegate={
        "calls":100,"raw_cpu_ns":100_000,
        "groups":[
            {"type":"EMPTY","calls":60,"raw_cpu_ns":1000},
            {"type":"net.minecraft.server.commands.ExecuteCommand$$Lambda",
             "calls":40,"raw_cpu_ns":99_000},
        ]
    }
    site={
        "mode":"timed","callbacks":100,"raw_cpu_ns":100_000,
        "java_thread_id":15,"nested":0,
        "sites":{
            "SCORE_STORE":{"calls":30,"raw_cpu_ns":80_000},
            "BOSSBAR_STORE":{"calls":5,"raw_cpu_ns":10_000},
            "DATA_STORE":{"calls":5,"raw_cpu_ns":9_000},
            "FUNCTION_CONDITION":{"calls":0,"raw_cpu_ns":0},
            "NO_SITE":{"calls":60,"raw_cpu_ns":1000},
            "MULTIPLE":{"calls":0,"raw_cpu_ns":0},
        },
    }
    data={"scheduler_result_site_trace_enabled":True,
          "scheduler_result_site_trace":site}
    return data,{"trace":delegate,
                 "cpu":{"server_thread_cpu_running_ns":12_000_000}}


class SiteCensusTests(unittest.TestCase):
    def test_exact_callback_owner_coverage_and_cpu_sums(self):
        d,parent=fixture()
        d["scheduler_result_site_trace"]["callbacks"]=300
        # 100 is below native parent power gate: use explicit 300-sample fixture.
        t=d["scheduler_result_site_trace"]
        for row in t["sites"].values():
            row["calls"]*=3
            row["raw_cpu_ns"]*=3
        t["raw_cpu_ns"]*=3
        parent["trace"]["calls"]*=3
        parent["trace"]["raw_cpu_ns"]*=3
        for group in parent["trace"]["groups"]:
            group["calls"]*=3
            group["raw_cpu_ns"]*=3
        with patch("ci_scheduler_result_sites.validate_native",return_value=parent):
            r=interpret(d)
        self.assertEqual(r["ExecuteCommand_owned_sampled_callbacks"],120)
        self.assertEqual(r["no_op_empty_sampled_callbacks"],180)
        self.assertEqual(r["synthetic_sites_by_raw_callback_cpu"][0]["site"],"SCORE_STORE")
        self.assertAlmostEqual(
            r["synthetic_sites_by_raw_callback_cpu"][0]
             ["share_of_ExecuteCommand_owned_sampled_cpu"],80_000/99_000)
        self.assertIn("NOT",r["limitations"])

    def test_misclassified_owner_is_rejected(self):
        d,parent=fixture()
        d["scheduler_result_site_trace"]["callbacks"]=300
        for row in d["scheduler_result_site_trace"]["sites"].values():
            row["calls"]*=3
            row["raw_cpu_ns"]*=3
        d["scheduler_result_site_trace"]["raw_cpu_ns"]*=3
        parent["trace"]["calls"]*=3
        parent["trace"]["raw_cpu_ns"]*=3
        for group in parent["trace"]["groups"]:
            group["calls"]*=3
            group["raw_cpu_ns"]*=3
        d["scheduler_result_site_trace"]["sites"]["SCORE_STORE"]["calls"]-=1
        d["scheduler_result_site_trace"]["sites"]["NO_SITE"]["calls"]+=1
        with patch("ci_scheduler_result_sites.validate_native",return_value=parent):
            with self.assertRaises(AssertionError):interpret(d)

    def test_multiple_site_visits_are_invalid(self):
        d,parent=fixture()
        d["scheduler_result_site_trace"]["callbacks"]=300
        for row in d["scheduler_result_site_trace"]["sites"].values():
            row["calls"]*=3
            row["raw_cpu_ns"]*=3
        d["scheduler_result_site_trace"]["raw_cpu_ns"]*=3
        parent["trace"]["calls"]*=3
        parent["trace"]["raw_cpu_ns"]*=3
        for group in parent["trace"]["groups"]:
            group["calls"]*=3
            group["raw_cpu_ns"]*=3
        d["scheduler_result_site_trace"]["sites"]["SCORE_STORE"]["calls"]-=1
        d["scheduler_result_site_trace"]["sites"]["MULTIPLE"]["calls"]=1
        with patch("ci_scheduler_result_sites.validate_native",return_value=parent):
            with self.assertRaises(AssertionError):interpret(d)

if __name__=="__main__":
    unittest.main()
