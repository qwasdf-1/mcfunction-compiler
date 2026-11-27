"""IR048 bounded dispatch and initial semantic protocol contracts."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/functioncompiler"
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir048 as native
class IR048(unittest.TestCase):
    def test_native_authority(self):
        s=(JAVA/"TypedContextDispatch.java").read_text()
        for token in ("ContextChain.runModifier(stage, source","context.incrementCost()",
                      "ExecutionControl.create(context, frame)","executor.run(transformed, terminal, FORKED, control)",
                      "next.size() + out.size() >= limit","source.handleError(error, true",
                      "source.callback() != CommandResultCallback.EMPTY","context.tracer() != null",
                      "context.forkLimit() <= 1","original.execute(source, context, frame)",
                      "List.copyOf(stages)","getNestHost()"):
            self.assertIn(token,s)
        for token in ("new CallFunction","new ExecuteCommand","functionCompiler$setCommand","findEntities(","withEntity(","withPosition("):
            self.assertNotIn(token,s)
        self.assertIn("TypedContextCallBoundary",(JAVA/"MixedFunctionIR.java").read_text())
        self.assertNotIn('"FC_TYPED_IR_CONTEXT_DISPATCH"',(JAVA/"TypedCompilerConfiguration.java").read_text())
    def test_protocol(self):
        self.assertEqual(native.options("old_bytecode")["FC_TYPED_IR_CONTEXT_DISPATCH"],"false")
        self.assertEqual(native.options("bytecode")["FC_TYPED_IR_CONTEXT_DISPATCH"],"true")
        self.assertEqual(native.expected("at",3,1)["#order"],123)
        self.assertEqual(native.expected("after",3,1)["#order"],23)
        self.assertEqual(native.expected("before",3,0)["#calls"],0)
        self.assertIn(1,native.QUOTAS)
        self.assertIn(65536,native.QUOTAS)
if __name__=="__main__":unittest.main()
