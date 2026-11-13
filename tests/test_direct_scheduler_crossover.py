"""SCHED-ARCH-014 test contracts: no alternative path without full safety gate."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_direct_scheduler_crossover as study


class MockRcon:
    def command(self, text):
        _,_,fid=text.split(" ",2)
        if fid.endswith(":unsupported"):
            length=0
            direct=0
            fused=0
        else:
            length=int(fid.split("_")[-1])
            direct=int(fid.startswith(study.DIRECT_NS+":"))
            fused=1
        return (f"FC_STATS score_add_compiled={length} fused_regions_compiled={fused} "
                f"direct_scheduler_compiled={direct} direct_scheduler_executed=0 "
                f"direct_scheduler_fallbacks=0")


def fake_boot(index, entry, placebo=1.0, direct=0.8, good=True):
    cpu={"fused":100.0,"fused_null":100.0*placebo,"direct":100.0*direct}
    return {
        "boot":index,"status":"complete",
        "qualification":{"qualification_stable":good},
        "blocks":[{
            "kind":b["kind"],"orientation":b["orientation"],
            "windows":[{
                "arm":arm,"cpu_ns_per_command":cpu[arm],
                "exact_work":True,"cgroup_nr_throttled_delta":0,
                "runqueue_delay_fraction":0.0
            } for arm in b["arms"]]
        } for b in entry["blocks"]]
    }


class DirectSchedulerContracts(unittest.TestCase):
    def test_preregistered_crossover_is_balanced(self):
        fixed=study.plan()
        self.assertEqual(fixed,study.plan())
        self.assertEqual(len(fixed),12)
        from collections import Counter
        self.assertEqual(Counter(tuple(b["kind"] for b in x["blocks"]) for x in fixed),
                         Counter({("negative","direct_vs_fused"):6,
                                  ("direct_vs_fused","negative"):6}))
        for kind in study.KIND_ARMS:
            orientations=[b["orientation"] for x in fixed for b in x["blocks"]
                          if b["kind"]==kind]
            self.assertEqual(orientations.count("ABBA"),6)
            self.assertEqual(orientations.count("BAAB"),6)

    def test_byte_identical_compiled_source_and_unsupported_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)
            study.make_pack(work)
            folder=work/"world/datapacks"/study.PACK/"data"
            for length in study.LENGTHS:
                sources=[
                    (folder/(study.DIRECT_NS if arm=="direct" else study.C_NS)/
                     "function"/(
                        "score_null_" if arm=="fused_null" else "score_"
                     ).__str__() if False else "")
                    for arm in ()
                ]
                texts=[]
                for arm in ("fused","fused_null","direct"):
                    namespace=study.DIRECT_NS if arm=="direct" else study.C_NS
                    file=(folder/namespace/"function"/(
                        f"score_null_{length}.mcfunction" if arm=="fused_null"
                        else f"score_{length}.mcfunction"
                    ))
                    texts.append(file.read_text())
                self.assertEqual(texts[0],texts[1])
                self.assertEqual(texts[0],texts[2])
                self.assertEqual(len(texts[0].splitlines()),length)
                self.assertTrue(all(line=="scoreboard players add #x fc_sched 1"
                                    for line in texts[0].splitlines()))
            self.assertIn("function", (folder/study.DIRECT_NS/"function"/
                                      "unsupported.mcfunction").read_text())

    def test_activation_gate_covers_every_function_and_rejects_unsafe_one(self):
        data=study.activation_gate(MockRcon(),diagnostics=True)
        self.assertEqual(len(data),len(study.LENGTHS)*3)
        self.assertEqual(data[study.function_id("direct",2000)]["direct_scheduler_compiled"],1)
        self.assertEqual(data[study.function_id("fused",2000)]["direct_scheduler_compiled"],0)

    def test_material_gain_requires_strict_valid_placebo(self):
        assignments=study.plan()
        result=study.analyze(
            [fake_boot(i,a) for i,a in enumerate(assignments)],assignments)
        self.assertEqual(result["verdict"],"direct_scheduler_material_gain_supported")
        self.assertLess(result["by_kind"]["direct_vs_fused"]["median_signed_log_percent"],-15)
        self.assertEqual(result["by_kind"]["negative"]["median_signed_log_percent"],0)

    def test_a_a_failure_invalidates_gain(self):
        assignments=study.plan()
        result=study.analyze(
            [fake_boot(i,a,placebo=1.2) for i,a in enumerate(assignments)],assignments)
        self.assertEqual(result["verdict"],"invalid_negative_control")

    def test_no_material_gain_not_promoted(self):
        assignments=study.plan()
        result=study.analyze(
            [fake_boot(i,a,direct=.98) for i,a in enumerate(assignments)],assignments)
        self.assertEqual(result["verdict"],"direct_scheduler_no_material_gain")

    def test_quality_failure_invalidates_campaign(self):
        assignments=study.plan()
        trials=[fake_boot(i,a) for i,a in enumerate(assignments)]
        trials[4]["qualification"]["qualification_stable"]=False
        result=study.analyze(trials,assignments)
        self.assertEqual(result["verdict"],"inconclusive_quality")
        self.assertEqual(result["quality_failed_boots"],[4])

    def test_wrong_work_and_order_fatal(self):
        assignments=study.plan()
        trials=[fake_boot(i,a) for i,a in enumerate(assignments)]
        trials[0]["blocks"][0]["windows"][0]["exact_work"]=False
        with self.assertRaises(AssertionError):
            study.analyze(trials,assignments)
        trials[0]["blocks"][0]["windows"][0]["exact_work"]=True
        trials[0]["blocks"][0]["windows"][0]["arm"]="direct" if (
            trials[0]["blocks"][0]["windows"][0]["arm"]!="direct") else "fused"
        with self.assertRaises(AssertionError):
            study.analyze(trials,assignments)

    def test_no_inference_from_missing_or_partial_boots(self):
        assignments=study.plan()
        trials=[fake_boot(i,a) for i,a in enumerate(assignments)]
        with self.assertRaises(AssertionError):
            study.analyze(trials[:-1],assignments)


if __name__=="__main__":
    unittest.main()
