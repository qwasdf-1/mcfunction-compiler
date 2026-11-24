"""IR040 source contracts and benchmark protocol, not a timing substitute."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/functioncompiler"
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir040 as native
import ci_typed_ir040_cpu as cpu

def src(name):return (JAVA/name).read_text()

class IR040(unittest.TestCase):
    def test_absence_and_reversed_relations(self):
        facts=src("PredicateFacts.java")
        for x in ("ABSENT = 8","boolean absent","Domain intersect","Domain present()",
                  "left > right","EQ | ABSENT","accepted & ABSENT"):
            self.assertIn(x,facts)
        plan=src("CompoundScoreIR.java")
        self.assertIn("PredicateFacts.Flow",plan)
        self.assertIn("flow.range(left",plan)
        self.assertIn("flow.comparison(left, right",plan)
        self.assertIn("dataflowProven",plan)

    def test_cache_scoped_to_guard_read(self):
        runtime=src("TypedScoreIRRuntime.java")
        self.assertIn("compoundVisited = compoundPresent = 0",runtime)
        self.assertIn("compoundValues[index] = info.value()",runtime)
        self.assertIn("compoundPresent |= bit",runtime)
        terminal=runtime.split("boolean compoundTerminal()",1)[1].split("boolean completeCompound()",1)[0]
        self.assertNotIn("compoundValues",terminal)
        self.assertIn("getOrCreatePlayerScore",terminal)

    def test_arithmetic_native_operation_no_replay_and_swap_effect(self):
        ir=src("TypedScoreIR.java")
        self.assertIn("if (operation == BinaryOperator.SWAP) writes.add(source)",ir)
        runtime=src("TypedScoreIRRuntime.java")
        op=runtime.split("void applyNativeArithmetic()",1)[1].split("void finish(",1)[0]
        self.assertIn("nativeOperation().apply(access, sourceAccess)",op)
        self.assertIn("catch (CommandSyntaxException error)",op)
        self.assertIn("clearCurrent()",op)
        self.assertNotIn("original(",op)
        self.assertIn('"applyNativeArithmetic", "()V"',src("TypedScoreIRBytecode.java"))

    def test_flags_and_cpu_crossover(self):
        self.assertEqual(len(cpu.COMMANDS),64)
        self.assertEqual(cpu.BOOTS,2)
        self.assertEqual(cpu.AA_LIMIT,.05)
        self.assertIn(("native","native"),cpu.COMPARISONS)
        self.assertIn(("base","base"),cpu.COMPARISONS)
        self.assertEqual(native.options("old_bytecode")["FC_TYPED_IR_COMPOUND_SCORE"],"true")
        for k in ("FC_TYPED_IR_DATAFLOW","FC_TYPED_IR_ARITHMETIC"):
            self.assertEqual(native.options("old_bytecode")[k],"false")
            self.assertEqual(native.options("bytecode")[k],"true")
        self.assertEqual(cpu.options("bytecode")["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(cpu.options("bytecode")["FC_TYPED_IR040_BENCHMARK"],"true")

if __name__=="__main__":unittest.main()
