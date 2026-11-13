"""Contracts for SCHED-ARCH-013's real A/A, A/B, B/C attribution design."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_scheduler_arch_attribution as a


class FakeStatsRcon:
    def command(self, cmd):
        _,_,function_id=cmd.split(" ",2)
        namespace,name=function_id.split(":",1)
        length=int(name.split("_")[-1])
        if namespace in (a.NAMESPACES["native"],a.NAMESPACES["null"]):
            score,fused=0,0
        elif namespace==a.NAMESPACES["typed"]:
            score,fused=length,0
        else:
            score,fused=length,1
        return f"FC_STATS function={function_id} score_add_compiled={score} fused_regions_compiled={fused}"


def synthetic_boot(index, assignment, *, typed_multiplier=1.15,
                   fused_multiplier=.7, placebo_multiplier=1.0,
                   qualified=True):
    costs={"native":100.0,"null":100.0*placebo_multiplier,
           "typed":100.0*typed_multiplier,
           "fused":100.0*typed_multiplier*fused_multiplier}
    blocks=[]
    for block in assignment["blocks"]:
        windows=[{
            "arm":arm,
            "cpu_ns_per_command":costs[arm],
            "exact_work":True,
            "runqueue_delay_fraction":0.0,
            "cgroup_nr_throttled_delta":0,
        } for arm in block["arms"]]
        blocks.append({"kind":block["kind"],"orientation":block["orientation"],
                       "windows":windows})
    return {"index":index,"status":"complete","blocks":blocks,
            "qualification":{"qualification_stable":qualified}}


class SchedulerArchitectureTests(unittest.TestCase):
    def test_preregistered_plan_is_balanced(self):
        x=a.plan()
        self.assertEqual(x,a.plan())
        self.assertEqual(len(x),12)
        self.assertEqual([p["boot"] for p in x],list(range(12)))
        for kind in a.KINDS:
            slots=[block["orientation"] for p in x for block in p["blocks"]
                   if block["kind"]==kind]
            self.assertEqual(slots.count("ABBA"),6)
            self.assertEqual(slots.count("BAAB"),6)
        from collections import Counter
        self.assertTrue(all(v==2 for v in Counter(
            tuple(block["kind"] for block in p["blocks"])
            for p in x).values()))

    def test_fixture_is_identical_within_length_and_uses_no_direct_scheduler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            a.prepare_fixture(root)
            dp=root/"world/datapacks"/a.PACK
            for n in a.LENGTHS:
                files=[(dp/"data"/name/"function"/f"score_{n}.mcfunction").read_text()
                       for name in a.NAMESPACES.values()]
                self.assertTrue(all(x==files[0] for x in files))
                self.assertEqual(len(files[0].splitlines()),n)
                self.assertTrue(all(line.startswith("scoreboard players add")
                                    for line in files[0].splitlines()))
            self.assertFalse((root/"world/datapacks"/a.PACK).is_file())

    def test_compiler_arming_requires_correct_count_for_all_16_functions(self):
        measurements=a.compilation_gate(FakeStatsRcon())
        self.assertEqual(len(measurements),len(a.LENGTHS)*len(a.NAMESPACES))
        self.assertEqual(measurements[a.function_id("fused",2000)]["fused_regions_compiled"],1)

    def test_analysis_reports_incremental_b_and_c_without_d(self):
        assignment=a.plan()
        runs=[synthetic_boot(i,assignment[i]) for i in range(a.N_BOOTS)]
        result=a.analyze(runs,assignment)
        self.assertEqual(result["verdict"],"valid_a_b_c_comparison")
        self.assertEqual(result["by_kind"]["negative"]["median_signed_log_percent"],0)
        self.assertGreater(result["by_kind"]["typed_vs_native"]["exact_median_interval"]["lower"],0)
        self.assertLess(result["by_kind"]["fusion_vs_typed"]["exact_median_interval"]["upper"],0)
        self.assertIn("UNMEASURED",result["prohibited_inference"])

    def test_broken_placebo_not_reclassified_as_valid(self):
        assignment=a.plan()
        runs=[synthetic_boot(i,assignment[i],placebo_multiplier=1.2)
              for i in range(a.N_BOOTS)]
        self.assertEqual(a.analyze(runs,assignment)["verdict"],"invalid_a_a_control")

    def test_quality_failures_cannot_be_dropped(self):
        assignment=a.plan()
        runs=[synthetic_boot(i,assignment[i]) for i in range(a.N_BOOTS)]
        runs[1]["qualification"]["qualification_stable"]=False
        result=a.analyze(runs,assignment)
        self.assertEqual(result["verdict"],"inconclusive_quality")
        self.assertEqual(result["quality_failed_boots"],[1])
        self.assertEqual(len(result["per_boot"]),12)

    def test_missing_work_rejected(self):
        assignment=a.plan()
        runs=[synthetic_boot(i,assignment[i]) for i in range(a.N_BOOTS)]
        runs[2]["blocks"][1]["windows"][0]["exact_work"]=False
        with self.assertRaises(AssertionError):
            a.analyze(runs,assignment)

    def test_wrong_crossover_order_rejected(self):
        assignment=a.plan()
        runs=[synthetic_boot(i,assignment[i]) for i in range(a.N_BOOTS)]
        runs[0]["blocks"][0]["windows"][0]["arm"]="fused"
        with self.assertRaises(AssertionError):
            a.analyze(runs,assignment)

    def test_misleading_status_substring_is_not_parsed(self):
        self.assertEqual(a.parse_stat("FC_PROBE arch_quota_debits=17", "arch_quota_debits"),17)
        with self.assertRaises(AssertionError):
            a.parse_stat("FC_PROBE arch_quota_debits_fake=17", "arch_quota_debits")


if __name__ == "__main__":
    unittest.main()
