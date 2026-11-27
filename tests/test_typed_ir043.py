"""IR043 typed call boundary and protocol contracts."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/functioncompiler"
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir043 as native
import ci_typed_ir043_cpu as cpu

class IR043(unittest.TestCase):
    def test_native_custom_terminal_and_boundary(self):
        source=(JAVA/"TypedFunctionDispatch.java").read_text()
        for token in ("CustomCommandExecutor<CommandSourceStack>","ExecutionControl.create(context, frame)",
                      "executor.run(source, terminal, modifiers", "original.execute(source, context, frame)",
                      "source.callback() != CommandResultCallback.EMPTY","context.forkLimit() <= 1",
                      "context.incrementCost()","if (!pass)","preparePredicates(predicates"):
            self.assertIn(token,source)
        self.assertNotIn("new CallFunction",source)
        self.assertNotIn("new ExecuteCommand",source)
        self.assertNotIn("functionCompiler$setCommand",source)
        mixed=(JAVA/"MixedFunctionIR.java").read_text()
        self.assertIn("record TypedCallBoundary",mixed)
        self.assertIn("nodes.add(new TypedCallBoundary(index, call, call))",mixed)
        self.assertIn("typedSourceCount() != sourceCount",mixed)
        ir=(JAVA/"TypedScoreIR.java").read_text()
        self.assertIn("mixed.typedCallCount() == 0",ir)
        self.assertIn("TypedFunctionDispatch.diagnostics()",ir)

    def test_native_regression(self):
        self.assertEqual(native.options("old_bytecode")["FC_TYPED_IR_DISPATCH"],"false")
        self.assertEqual(native.options("bytecode")["FC_TYPED_IR_DISPATCH"],"true")
        self.assertEqual(native.options("direct")["FC_TYPED_IR_DIRECT_FUNCTION"],"true")
        for k in ("ir019_ir043_recursive","ir019_ir043_callback","ir019_ir043_objective",
                  "ir019_ir043_missing_function","ir019_ir043_return","ir019_ir043_opaque"):
            self.assertIn(k,native.ROOTS)
        self.assertEqual(native.LAYOUTS["ir019_ir043_opaque"],0)
        self.assertEqual(native.LAYOUTS["ir019_ir043_return"],0)
        self.assertIn(1,native.QUOTAS)
        self.assertIn(128,native.QUOTAS)

    def test_cpu_identical_work_and_gate(self):
        self.assertEqual(len(cpu.SOURCE),64)
        self.assertEqual(cpu.CHILD,["scoreboard players add #x fc_ir 1"])
        self.assertEqual(cpu.ARMS,("native","typed"))
        self.assertEqual(cpu.protocol.MIN_CPU_NS,500_000_000)
        self.assertEqual(cpu.protocol.STABLE_WINDOWS,6)
        self.assertEqual(cpu.options("bytecode")["FC_TYPED_IR_DIAGNOSTICS"],"false")

if __name__=="__main__":unittest.main()
