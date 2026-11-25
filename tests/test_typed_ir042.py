"""IR042 fixed gates, source join and benchmark isolation contracts."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir042_attribution as attr
import ci_typed_ir042_publisher as pub

def sample(cost=100):
    return {"cpu_ns":int(cost*10_000_000),"top_level_lines":10_000_000}

def block(a,b,reduction):
    return {"a":a,"b":b,"reduction":reduction,"samples":[sample()]*4,
            "a_ns_per_line":100,"b_ns_per_line":100*(1-reduction)}

class IR042(unittest.TestCase):
    def test_fixed_calibration_and_isolation(self):
        self.assertEqual(attr.MIN_CPU_NS,500_000_000)
        self.assertEqual(attr.STABLE_WINDOWS,6)
        self.assertEqual(attr.HOLDOUT_ROUNDS,2)
        self.assertEqual(attr.BOOTS,2)
        self.assertEqual(attr.ARMS,("native","interp","base","flow","direct"))
        self.assertEqual(attr.options("bytecode")["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(attr.options("bytecode")["FC_IR041_COMPILE_TIMING"],"false")
        for arm in attr.ARMS:self.assertIn((arm,arm),attr.PAIRS)
        for pair in attr.CONTRASTS:self.assertIn(pair,attr.PAIRS)
        self.assertEqual(len(attr.SOURCE),64)
        self.assertLess(attr.CALLS*64*5+attr.CALLS,1_000_000)

    def test_warmup_and_placebo_never_relaxed(self):
        h={a:[sample()]*6 for a in attr.ARMS}
        self.assertTrue(attr.qualified(h))
        h["direct"][-1]=sample(40)
        self.assertFalse(attr.qualified(h))
        self.assertFalse(attr.aa_pass([block("native","native",.051)]))
        self.assertTrue(attr.aa_pass([block("base","base",-.03)]))

    def test_profitability_requires_qualified_speedup(self):
        blocks=[block("native","native",.01),block("native","flow",.5),
                block("native","flow",.52),block("base","flow",-.02),block("base","flow",.01)]
        boots=[{"status":"complete","blocks":list(blocks)} for _ in range(2)]
        phases={"fc_ir:ir017_ir040_perf":{"adapter":{"cpu_ns":1_000_000},"typed":{"cpu_ns":2_000_000}}}
        good=attr.analyze(boots,phases)["findings"]
        self.assertTrue(good["native_vs_flow"]["pilot_gate_pass"])
        self.assertIn("illustrative_post_parse_break_even_calls",good["native_vs_flow"])
        self.assertFalse(good["base_vs_flow"]["pilot_gate_pass"])
        boots[1]["status"]="measurement_placebo_failed"
        bad=attr.analyze(boots,phases)["findings"]["native_vs_flow"]
        self.assertFalse(bad["pilot_gate_pass"])
        self.assertNotIn("illustrative_post_parse_break_even_calls",bad)

    def test_static_region_join_and_rank(self):
        line="scoreboard players add #x obj 1"
        self.assertEqual(pub.regions([line]*65),set(range(64)))
        self.assertEqual(pub.regions([line,"function a:b",line]),set())
        self.assertEqual(pub.opportunity(line),"isolated_typed_candidate")
        self.assertEqual(pub.opportunity("execute if score #x obj matches 1 run function a:b"),"function_dispatch")
        self.assertEqual(pub.opportunity("execute as @e run scoreboard players add @s obj 1"),"entity_context_or_selector")
        self.assertEqual(pub.opportunity("execute store result score #x obj run data get storage a:b x"),"data_or_store")

    def test_publisher_instrumentation_off_in_timing(self):
        self.assertEqual(pub.options("native")["FC_COMPILER_EXEC_CENSUS"],"false")
        self.assertEqual(pub.options("native")["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(pub.options("native")["FC_IR041_COMPILE_TIMING"],"false")
        self.assertEqual(pub.options("native")["FC_TYPED_IR_MODE"],"")
        self.assertEqual(pub.AA_LIMIT,.05)
        self.assertEqual(pub.TICKS,600)
if __name__=="__main__":unittest.main()
