"""IR045 contract and acceptance protocol checks."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir045 as native
import ci_typed_ir045_cpu as cpu
import ci_typed_ir045_publisher as pub
class IR045(unittest.TestCase):
    def test_native_authority(self):
        java=ROOT/"src/main/java/dev/functioncompiler"
        source=(java/"TypedNativeStore.java").read_text()
        for token in ("ContextChain.runModifier(modifier, source","context.incrementCost()",
                      "terminal.bind(","context.tracer() != null","context.forkLimit() <= 1",
                      "original.execute(source, context, frame)","CustomModifierExecutor",
                      "CustomCommandExecutor","getNestHost()","ContinuationTask.schedule"):
            self.assertIn(token,source)
        for token in ("functionCompiler$setCommand","new CallFunction","getOrCreatePlayerScore","getBlockState","withCallback("):
            self.assertNotIn(token,source)
        self.assertIn("TypedStoreBoundary",(java/"MixedFunctionIR.java").read_text())
    def test_scope(self):
        for line in ("execute store success score @s erb.tmp run data modify entity @s data.saved_nbt set from block ~ ~ ~ {}",
                     "execute store result score #x erb.tmp run data get entity @s Pos[0] 1",
                     "execute store result score #r obj run data get storage a:b value 1"):
            self.assertEqual(pub.kind(line),"T")
        for line in ("execute as @s store result score #x obj run data get entity @s Pos[0] 1",
                     "execute store result storage a:b x int 1 run scoreboard players add #x obj 1",
                     "execute store result score #x obj run return 7"):
            self.assertNotEqual(pub.kind(line),"T")
        self.assertEqual(native.options("old_bytecode")["FC_TYPED_IR_NATIVE_STORE"],"false")
        self.assertEqual(native.options("direct")["FC_TYPED_IR_NATIVE_STORE"],"true")
    def test_fixed_cpu(self):
        self.assertEqual(len(cpu.SOURCE),64)
        self.assertEqual(cpu.protocol.MIN_CPU_NS,500_000_000)
        self.assertEqual(cpu.protocol.STABLE_WINDOWS,6)
        self.assertEqual(cpu.protocol.HOLDOUT_ROUNDS,2)
        self.assertEqual(cpu.options("bytecode")["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(cpu.ARMS,("native","typed"))
if __name__=="__main__":unittest.main()
