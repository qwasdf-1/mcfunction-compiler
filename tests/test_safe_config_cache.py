"""SCHED-COMP-016 experimental contracts and semantic-gate regression checks."""
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_safe_config_cache as a


class FakeStats:
    def command(self,text):
        _,_,fid=text.split(" ",2)
        ns,name=fid.split(":",1)
        n=int(name.split("_")[-1])
        score=0 if ns in (a.NS["native"],a.NS["null"]) else n
        return f"FC_STATS function={fid} score_add_compiled={score}"


def synthetic(i,assignment,placebo=1.0,legacy=1.5,cached=.90,qualified=True):
    costs={"native":100.0,"null":100.0*placebo,
           "legacy":100.0*legacy,"cached":100.0*cached}
    return {"index":i,"status":"complete",
            "qualification":{"qualification_stable":qualified},
            "blocks":[{
                "kind":b["kind"],"orientation":b["orientation"],
                "windows":[{
                    "arm":arm,"cpu_ns_per_command":costs[arm],
                    "cgroup_nr_throttled_delta":0,
                    "runqueue_delay_fraction":0.0,"exact_work":True
                } for arm in b["arms"]]
            } for b in assignment["blocks"]]}


class SafeConfigCacheContracts(unittest.TestCase):
    def test_plan_balanced(self):
        p=a.plan()
        self.assertEqual(p,a.plan())
        self.assertEqual(len(p),12)
        by_order=Counter(tuple(b["kind"] for b in r["blocks"]) for r in p)
        self.assertEqual(len(by_order),4)
        self.assertTrue(all(v==3 for v in by_order.values()))
        for kind in a.KINDS:
            self.assertEqual(Counter(b["orientation"] for r in p
                for b in r["blocks"] if b["kind"]==kind),{"ABBA":6,"BAAB":6})
            self.assertEqual(Counter(i for r in p for i,b in enumerate(r["blocks"])
                if b["kind"]==kind),{0:3,1:3,2:3,3:3})

    def test_all_source_work_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            a.prepare(work)
            pack=work/"world/datapacks"/a.PACK
            for n in a.LENGTHS:
                data=[(pack/"data"/ns/"function"/f"score_{n}.mcfunction").read_text()
                      for ns in a.NS.values()]
                self.assertEqual(len(set(data)),1)
                self.assertEqual(len(data[0].splitlines()),n)
            config=(work/"config/function-compiler.json").read_text()
            self.assertIn('"fused_regions": false',config)

    def test_compile_activation(self):
        observed=a.activation(FakeStats())
        self.assertEqual(len(observed),len(a.LENGTHS)*len(a.NS))
        self.assertEqual(observed[a.fid("legacy",2000)],2000)
        self.assertEqual(observed[a.fid("cached",2000)],2000)
        self.assertEqual(observed[a.fid("native",2000)],0)

    def test_a_a_valid_and_direct_cached_vs_native(self):
        p=a.plan()
        runs=[synthetic(i,item) for i,item in enumerate(p)]
        result=a.analyze(runs,p)
        self.assertEqual(result["verdict"],"cached_path_small_gain_vs_native_supported")
        self.assertTrue(result["negative_interval_includes_zero"])
        self.assertLess(result["by_kind"]["cached_vs_legacy"]["exact_median_interval"]["upper"],0)
        self.assertLess(result["by_kind"]["cached_vs_native"]["exact_median_interval"]["upper"],0)

    def test_native_placebo_imbalance_invalidates_other_gains(self):
        p=a.plan()
        runs=[synthetic(i,item,placebo=1.20) for i,item in enumerate(p)]
        self.assertEqual(a.analyze(runs,p)["verdict"],"invalid_a_a_control")

    def test_quality_failure_and_missing_work(self):
        p=a.plan()
        runs=[synthetic(i,item) for i,item in enumerate(p)]
        runs[3]["qualification"]["qualification_stable"]=False
        self.assertEqual(a.analyze(runs,p)["verdict"],"inconclusive_quality")
        runs[3]["qualification"]["qualification_stable"]=True
        runs[0]["blocks"][0]["windows"][0]["exact_work"]=False
        with self.assertRaises(AssertionError):a.analyze(runs,p)

    def test_partial_and_order_invalid(self):
        p=a.plan()
        runs=[synthetic(i,item) for i,item in enumerate(p)]
        with self.assertRaises(AssertionError):a.analyze(runs[:-1],p)
        runs[0]["blocks"][0]["windows"][0]["arm"]="not-a-declared-arm"
        with self.assertRaises(AssertionError):a.analyze(runs,p)

    def test_gamerule_readback_requires_correct_name_and_numeric_value(self):
        class InvalidRule:
            def command(self,_):
                return "Unknown gamerule"
        with self.assertRaises(AssertionError):a.read_quota(InvalidRule())
        class Valid:
            def command(self,_):
                return f"Game rule {a.RULE} is currently set to 42"
        self.assertEqual(a.read_quota(Valid()),42)

    def test_reload_config_path_writes_dynamic_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            a.prepare(root)
            a.rewrite_config(root,False)
            import json
            data=json.loads((root/"config/function-compiler.json").read_text())
            self.assertTrue(data["enabled"])
            self.assertFalse(data["score_add"])
            a.rewrite_config(root,True)
            data=json.loads((root/"config/function-compiler.json").read_text())
            self.assertTrue(data["score_add"])

if __name__=="__main__":
    unittest.main()
