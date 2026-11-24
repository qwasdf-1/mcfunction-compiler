"""IR041 tests the measurement gate independently from Minecraft timing."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_typed_ir041 as p
import ci_typed_ir041_source as source

def sample(cost=100):
    return {"cpu_ns":int(cost*524288),"top_level_lines":524288}

def block(a,b,reduction):
    return {"a":a,"b":b,"reduction":reduction,"samples":[sample()]*4}

class IR041(unittest.TestCase):
    def test_budget_and_mixed_work(self):
        self.assertEqual(p.CALLS*p.BATCHES*p.LINES["compound"],524288)
        self.assertEqual(p.LINES["mixed"],64)
        self.assertEqual(p.NESTED["mixed"],4)
        self.assertEqual(sum(1+2*(i>=5)+4*(5<=i<=7)+8 for i in range(1,9)),92)
        self.assertEqual(p.options("bytecode")["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(p.options("bytecode")["FC_IR041_COMPILE_TIMING"],"false")
        self.assertEqual(p.BOOTS,2)

    def test_qualification_requires_consecutive_stability(self):
        h={a:[sample() for _ in range(p.MIN_ROUNDS-1)] for a in p.ARMS}
        self.assertFalse(p.qualify(h))
        for a in p.ARMS:h[a].append(sample())
        self.assertTrue(p.qualify(h))
        h["base"][-1]=sample(110)
        self.assertFalse(p.qualify(h))
        h["base"][-1]=sample(1)
        self.assertFalse(p.qualify(h))

    def test_placebo_gate_and_acceptance(self):
        self.assertFalse(p.aa_pass([]))
        self.assertFalse(p.aa_pass([block("native","native",.06)]))
        self.assertTrue(p.aa_pass([block("native","native",.01)]))
        blocks=[block("native","native",.01),block("base","base",-.01),block("flow","flow",0),
                block("native","flow",.4),block("native","flow",.3),
                block("base","flow",.1),block("base","flow",.12)]
        boots=[{"workloads":{"mixed":{"status":"complete","blocks":list(blocks)}}} for _ in range(2)]
        self.assertTrue(p.analyze_workload("mixed",boots)["findings"]["native_vs_flow"]["pilot_gate_pass"])
        boots[1]["workloads"]["mixed"]["status"]="measurement_placebo_failed"
        self.assertFalse(p.analyze_workload("mixed",boots)["findings"]["native_vs_flow"]["pilot_gate_pass"])
        boots[1]["workloads"]["mixed"]["status"]="complete"
        boots[1]["workloads"]["mixed"]["blocks"].append(block("flow","flow",.06))
        self.assertFalse(p.analyze_workload("mixed",boots)["findings"]["native_vs_flow"]["pilot_gate_pass"])

    def test_publisher_screen_is_conservative(self):
        self.assertEqual(source.shape("scoreboard players operation #x o >< @s o"),"arithmetic")
        self.assertEqual(source.shape("execute if score #a o matches 5.. unless score @s o < #a o run scoreboard players add #x o 1"),"compound")
        self.assertIsNone(source.shape("execute if score #x o matches 5.. run scoreboard players operation #x o /= #a o"))
        self.assertIsNone(source.shape("execute as @e if score @s o matches 1 run scoreboard players add #x o 1"))
        self.assertIsNone(source.shape("execute if score #x o matches 1 run function x:y"))

if __name__=="__main__":unittest.main()
