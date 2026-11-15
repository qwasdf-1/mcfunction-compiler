"""Contracts for SCHED-COMP-015: no claims from invalid placebo or non-equivalent work."""
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_scoreadd_attribution as study


class MockStats:
    def command(self, cmd):
        _,_,fid=cmd.split(" ",2)
        namespace,name=fid.split(":",1)
        length=int(name.split("_")[-1])
        compiled=(0 if namespace in
                  (study.NAMESPACES["native"],study.NAMESPACES["null"]) else length)
        return (f"FC_STATS function={fid} score_add_compiled={compiled} "
                f"fused_regions_compiled=0")


def fake_boot(i, assignment, *, placebo=1.0, delegate=1.04,
              typed=1.45, cached=.85, fastobj=.96, qualified=True):
    costs={"native":100.0,"null":100.0*placebo,
           "delegate":100.0*delegate,"typed":100.0*typed,
           "cached":100.0*typed*cached,
           "fastobj":100.0*typed*cached*fastobj}
    blocks=[{"kind":block["kind"],"orientation":block["orientation"],
             "windows":[{
                 "arm":arm,"cpu_ns_per_command":costs[arm],
                 "cgroup_nr_throttled_delta":0,
                 "runqueue_delay_fraction":0.0,
                 "exact_work":True,
             } for arm in block["arms"]]}
            for block in assignment["blocks"]]
    return {"index":i,"status":"complete","blocks":blocks,
            "qualification":{"qualification_stable":qualified}}


class AttributionContracts(unittest.TestCase):
    def test_10_boot_latin_square_and_orientation_balance(self):
        p=study.plan()
        self.assertEqual(p,study.plan())
        self.assertEqual(len(p),10)
        orders=Counter(tuple(b["kind"] for b in x["blocks"]) for x in p)
        self.assertEqual(len(orders),5)
        self.assertTrue(all(v==2 for v in orders.values()))
        for kind in study.KINDS:
            orientations=Counter(
                b["orientation"] for x in p for b in x["blocks"]
                if b["kind"]==kind)
            self.assertEqual(orientations,{"ABBA":5,"BAAB":5})
            self.assertEqual(Counter(
                pos for x in p for pos,b in enumerate(x["blocks"])
                if b["kind"]==kind),
                {0:2,1:2,2:2,3:2,4:2})

    def test_byte_identical_arms_and_no_fused_functions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            study.prepare_fixture(root)
            dp=root/"world/datapacks"/study.PACK
            for n in study.LENGTHS:
                texts=[(dp/"data"/ns/"function"/f"score_{n}.mcfunction").read_text()
                       for ns in study.NAMESPACES.values()]
                self.assertEqual(len(set(texts)),1)
                self.assertEqual(len(texts[0].splitlines()),n)
            config=(root/"config/function-compiler.json").read_text()
            self.assertIn('"fused_regions": false',config)

    def test_correct_specializations_and_no_fusion(self):
        observations=study.compilation_gate(MockStats())
        self.assertEqual(len(observations),len(study.LENGTHS)*6)
        self.assertEqual(observations[study.function_id("typed",2000)]["score_add_compiled"],2000)
        self.assertEqual(observations[study.function_id("delegate",2000)]["score_add_compiled"],2000)
        self.assertEqual(observations[study.function_id("native",2000)]["score_add_compiled"],0)
        self.assertEqual(observations[study.function_id("fastobj",2000)]["fused_regions_compiled"],0)

    def test_validity_and_causal_contrasts(self):
        p=study.plan()
        boots=[fake_boot(i,a) for i,a in enumerate(p)]
        result=study.analyze(boots,p)
        self.assertEqual(result["verdict"],"valid_attribution_comparison")
        self.assertEqual(result["by_kind"]["negative"]["median_signed_log_percent"],0)
        self.assertGreater(result["by_kind"]["delegating_vs_native"]["exact_median_interval"]["lower"],0)
        self.assertGreater(result["by_kind"]["typed_vs_delegating"]["exact_median_interval"]["lower"],0)
        self.assertLess(result["by_kind"]["cached_vs_typed"]["exact_median_interval"]["upper"],0)
        self.assertLess(result["by_kind"]["fastobj_vs_cached"]["exact_median_interval"]["upper"],0)
        self.assertEqual(len(result["derived_exploratory_native_to_typed"]["per_boot_signed_log_percent"]),10)
        self.assertIn("nanoTime",result["prohibited_inference"])

    def test_placebo_fails_without_posthoc_rejection(self):
        p=study.plan()
        boots=[fake_boot(i,a,placebo=1.2) for i,a in enumerate(p)]
        self.assertEqual(study.analyze(boots,p)["verdict"],"invalid_a_a_control")

    def test_quality_and_work_gates_are_fatal_to_claims(self):
        p=study.plan()
        boots=[fake_boot(i,a) for i,a in enumerate(p)]
        boots[2]["qualification"]["qualification_stable"]=False
        self.assertEqual(study.analyze(boots,p)["verdict"],"inconclusive_quality")
        boots[2]["qualification"]["qualification_stable"]=True
        boots[0]["blocks"][0]["windows"][0]["exact_work"]=False
        with self.assertRaises(AssertionError):
            study.analyze(boots,p)
        boots[0]["blocks"][0]["windows"][0]["exact_work"]=True
        boots[0]["blocks"][0]["windows"][0]["arm"]="fastobj"
        with self.assertRaises(AssertionError):
            study.analyze(boots,p)

    def test_partial_campaign_inconclusive(self):
        p=study.plan()
        boots=[fake_boot(i,a) for i,a in enumerate(p)]
        with self.assertRaises(AssertionError):
            study.analyze(boots[:-1],p)

    def test_status_phases_exactly_parsed(self):
        data="FC_PROBE score_phase_samples=20 score_phase_objective_ns=42"
        self.assertEqual(study.parse_stat(data,"score_phase_objective_ns"),42)
        with self.assertRaises(AssertionError):
            study.parse_stat(data,"score_phase_feedback_ns")


if __name__=="__main__":
    unittest.main()
