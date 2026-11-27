"""IR044 scope and gate contract, independent of native runtime checks."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir044 as native
import ci_typed_ir044_cpu as cpu
import ci_typed_ir044_publisher as pub

class IR044(unittest.TestCase):
    def test_guard_scope_and_original_authority(self):
        java=ROOT/"src/main/java/dev/functioncompiler"
        source=(java/"TypedConditionalTerminal.java").read_text()
        for token in ("ContextChain.runModifier(guard, source","context.incrementCost()",
                      "terminal.bind(","source.callback() != CommandResultCallback.EMPTY",
                      "context.tracer() != null","context.forkLimit() <= 1",
                      "original.execute(source, context, frame)","CustomModifierExecutor",
                      "CustomCommandExecutor","getNestHost()","ContinuationTask.schedule"):
            self.assertIn(token,source)
        for token in ("functionCompiler$setCommand","new CallFunction","getPlayerScoreInfo","getBlockState"):
            self.assertNotIn(token,source)
        self.assertIn("TypedGuardBoundary",(java/"MixedFunctionIR.java").read_text())

    def test_lexical_screen_and_negative_controls(self):
        self.assertEqual(pub.kind("function erb:read"),"D")
        self.assertEqual(pub.kind("execute if score @s erb.tmp matches 1 run function erb:read"),"D")
        self.assertEqual(pub.kind("execute as @e at @s run function erb:read"),"other_dispatch")
        self.assertEqual(pub.kind("execute if block ~ ~ ~ #erb:late run tag @s add erb.late"),"G")
        self.assertEqual(pub.kind("execute if score @s erb.tmp matches 1 run tag @s add erb.late"),"G")
        self.assertNotEqual(pub.kind("execute if block ~ ~ ~ minecraft:stone run return run tag @s add erb.late"),"G")
        self.assertNotEqual(pub.kind("execute positioned 0 64 0 if block ~ ~ ~ minecraft:stone run tag @s add erb.late"),"G")
        self.assertEqual(native.options("old_bytecode")["FC_TYPED_IR_GUARD_TERMINAL"],"false")
        self.assertEqual(native.options("direct")["FC_TYPED_IR_GUARD_TERMINAL"],"true")

    def test_cpu_protocol(self):
        self.assertEqual(len(cpu.SOURCE),64)
        self.assertEqual(cpu.protocol.MIN_CPU_NS,500_000_000)
        self.assertEqual(cpu.protocol.STABLE_WINDOWS,6)
        self.assertEqual(cpu.protocol.HOLDOUT_ROUNDS,2)
        self.assertEqual(cpu.options("bytecode")["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(cpu.ARMS,("native","typed"))

if __name__=="__main__":unittest.main()
