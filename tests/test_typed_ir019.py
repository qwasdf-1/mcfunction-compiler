"""IR-019 candidate classifier, native guard/callee census and safety contracts."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir019_inventory as source
import ci_typed_ir019_native as native


class IR019SourceAndNative(unittest.TestCase):
    def test_strict_vs_complex_original_source_shapes(self):
        examples={
            "execute if score #g fc_ir matches 1..4 run function fc_ir:child":"single_score_static_child",
            "execute unless score @s erb.mode matches ..-1 run function erb:child":"single_score_static_child",
            "execute if score #g fc_ir matches 1 if score #a fc_ir matches 2 run function fc_ir:child":"complex_or_return_child",
            "execute if score #g fc_ir matches 1 run return run function fc_ir:child":"complex_or_return_child",
            "execute if score #g fc_ir matches 1..3 run scoreboard players add #x fc_ir 1":"other",
            "execute if score #g fc_ir matches 1..3 run function #fc_ir:mytag":"complex_or_return_child",
            "function fc_ir:child":"other",
        }
        for text,expected in examples.items():
            self.assertEqual(source.classify(text),expected,text)

    def test_passive_mixin_and_exact_callee_allowlist(self):
        census=(ROOT/"src/main/java/dev/functioncompiler/CompilerExecutionCensus.java").read_text()
        call=(ROOT/"src/main/java/dev/functioncompiler/mixin/CallFunctionMixin.java").read_text()
        for token in (
            "FC_COMPILER_EXEC_CENSUS_CALLEES",
            "MAX_CALLEE_IDS = 96",
            "BROAD_SCORE_DISPATCH",
            "SIMPLE_SCORE_DISPATCH",
            "FC_EXEC_CALLEE",
            "native_call_tasks=",
            "FC_EXEC_ROW",
            "dispatch_shape={}",
            "recordNativeCall(Identifier id)",
            "if (!ACTIVE || !CONFIGURED || id == null) return;",
            "CALLEES.contains(key)",
        ):
            self.assertIn(token,census)
        self.assertIn("CompilerExecutionCensus.recordNativeCall(function.id());",call)
        self.assertIn('@Inject(method = "execute", at = @At("HEAD"))',call)
        self.assertNotIn("ci.cancel()",census)
        self.assertNotIn("queueNext(",census)

    def test_native_original_function_staging_and_counters(self):
        self.assertEqual(native.MODES,("native","census","ir018"))
        self.assertEqual(len(native.QUOTAS),11)
        self.assertEqual(native.EXPECTED["ir019_single"]["#hit"],5)
        self.assertEqual(native.EXPECTED["ir019_chained"]["#chain"],7)
        self.assertEqual(native.EXPECTED["ir019_return"]["#return_child"],3)
        for mode in native.MODES:
            e=native.options(mode)
            self.assertEqual(e["FC_TYPED_IR_DISPATCH_TEST_HARNESS"],"true")
            self.assertEqual(e["FC_COMPILER_EXEC_CENSUS"],
                             "true" if mode=="census" else "false")
            self.assertEqual(e["FC_TYPED_IR_MODE"],
                             "bytecode" if mode=="ir018" else "")
            self.assertEqual(e["FC_TYPED_IR_DIRECT_FUNCTION"],"false")
            self.assertEqual(e["FC_SCORE_ADD_PROTOTYPE"],"false")
        with tempfile.TemporaryDirectory() as tmp:
            native.fixture(Path(tmp))
            folder=Path(tmp)/"world/datapacks"/native.PACK/"data/fc_ir/function"
            self.assertTrue((folder/"ir019_single.mcfunction").is_file())
            self.assertTrue((folder.parents[2]/"pack.mcmeta").is_file())
            for name,lines in native.FUNCTIONS.items():
                self.assertEqual((folder/(name+".mcfunction")).read_text().splitlines(),lines)

    def test_real_caller_child_semantics_stay_native(self):
        code=(ROOT/"src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        self.assertIn('System.getenv("FC_TYPED_IR_DISPATCH_TEST_HARNESS")',code)
        self.assertIn('id.getPath().matches("ir019_[a-z0-9_]+")',code)
        mixed=(ROOT/"src/main/java/dev/functioncompiler/MixedFunctionIR.java").read_text()
        self.assertIn("FUNCTION_DISPATCH",mixed)
        self.assertIn("isFunctionDispatch(entry)",mixed)
        self.assertIn("return null;",mixed)
        study=(ROOT/"scripts/ci_typed_ir019_native.py").read_text()
        self.assertIn('"compiled_dispatch_claim":False',study)
        self.assertIn('"performance_claim":False',study)
        self.assertIn("if value!=ref[k]",study)


if __name__=="__main__":
    unittest.main()
