"""SCHED-COMP-017: predeclared paired native mining and semantic validity gates."""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_veinminer_cache_event as a


def arm(name:str,seconds:float,state:int=215)->dict:
    return {"mode":name,"event_completion_seconds":seconds,
            "parity_state":{"ore":state},"vm_queue_score_add_compiled":123,
            "profile_valid":True,"exact_native_workload":True}


def campaign(cached_ratio=.9,legacy=3.0):
    pairs=[]
    for i,order in enumerate(a.allocation(),1):
        pairs.append({"index":i,"order":list(order),"arms":{
            "legacy":arm("legacy",legacy),
            "cached":arm("cached",legacy*cached_ratio),
        }})
    return pairs


class VeinMinerCacheContracts(unittest.TestCase):
    def test_pair_order_is_balanced_and_stable(self):
        pairs=a.allocation()
        self.assertEqual(pairs,a.allocation())
        self.assertEqual(len(pairs),10)
        self.assertEqual(Counter(pairs),{
            ("legacy","cached"):5,("cached","legacy"):5})

    def test_valid_negative_impact_not_misreported_as_improvement(self):
        result=a.analyze(campaign(1.08))
        self.assertEqual(result["verdict"],"real_event_regression_supported")
        self.assertGreater(result["primary"]["exact_median_interval_percent"]["lower"],0)

    def test_material_gain_and_small_gain_are_distinct(self):
        fast=a.analyze(campaign(.75))
        self.assertEqual(fast["verdict"],"material_15pct_real_event_gain_supported")
        slow=a.analyze(campaign(.98))
        self.assertEqual(slow["verdict"],"small_real_event_gain_supported")

    def test_source_state_divergence_fatal(self):
        pairs=campaign()
        pairs[3]["arms"]["cached"]["parity_state"]["ore"]=214
        with self.assertRaises(AssertionError):a.analyze(pairs)

    def test_missing_compiler_activation_fatal(self):
        pairs=campaign()
        pairs[0]["arms"]["legacy"]["vm_queue_score_add_compiled"]=0
        with self.assertRaises(AssertionError):a.analyze(pairs)

    def test_invalid_or_partial_native_event_fatal(self):
        pairs=campaign()
        pairs[8]["arms"]["cached"]["exact_native_workload"]=False
        with self.assertRaises(AssertionError):a.analyze(pairs)
        with self.assertRaises(AssertionError):a.analyze(campaign()[:-1])

    def test_arithmetic_effect_is_not_log_percent(self):
        self.assertAlmostEqual(a.paired_percentage(.9,1.0),-10.0)
        with self.assertRaises(AssertionError):a.paired_percentage(0,1)

if __name__=="__main__":
    unittest.main()
