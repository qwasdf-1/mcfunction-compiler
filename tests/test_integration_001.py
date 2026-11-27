"""Candidate packaging and opt-in boundary, distinct from archived research contracts."""
import json
import hashlib
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/functioncompiler"
class Integration(unittest.TestCase):
    def test_no_historical_observer_mixins(self):
        cfg=json.loads((ROOT/"src/main/resources/function_compiler.mixins.json").read_text())
        self.assertFalse(any(m.startswith("Compiler") for m in cfg["mixins"]))
        self.assertEqual(cfg["plugin"],"dev.functioncompiler.mixin.IntegrationMixinPlugin")
        self.assertFalse(list((JAVA/"mixin").glob("Compiler*.java")))
        for stem in ("CompilerExecutionCensus","CompilerAcceptanceAudit","CompilerSelector022Probe",
                     "CompilerTagMutation023Probe","CompilerMacroLoadCpuProbe","IR041CompileProbe"):
            self.assertFalse((JAVA/(stem+".java")).exists())
    def test_unqualified_modes_withdrawn(self):
        text=(JAVA/"TypedScoreIR.java").read_text()
        self.assertIn("SCORE_CACHE = false",text)
        self.assertIn("COST_SELECT = false",text)
        self.assertIn("ENABLED = false",(JAVA/"CompilerForkExecutor025.java").read_text())
        self.assertIn("NAMESPACE != null && !NAMESPACE.isBlank()",text)
    def test_frozen_reference_inputs(self):
        fixtures=ROOT/"tests/fixtures/compiler"
        hashes={"ir042-census.json":"5977367281d9c0958f5dbc3cabb7d22c65902373f71cf1871893a68d14c820a9",
                "ir047-native.json":"bbe9d3b49beba444643cd5f2ec224447c0404b9006cf7bbe0b3090613c3cc7c6"}
        for name,expected in hashes.items():
            self.assertEqual(hashlib.sha256((fixtures/name).read_bytes()).hexdigest(),expected)
        native=json.loads((fixtures/"ir047-native.json").read_text())
        self.assertEqual(native["status"],"accepted")
        self.assertEqual(len(native["arms"]),5)
        self.assertTrue(all(len(a["cases"])==670 for a in native["arms"]))
    def test_fixture_mixins_gated(self):
        plugin=(JAVA/"mixin/IntegrationMixinPlugin.java").read_text()
        for flag in ("FC_TYPED_IR046_TEST_OBSERVER","FC_TYPED_IR047_TEST_OBSERVER","FC_TYPED_IR_REENTRANT_TEST_OBSERVER"):
            self.assertIn(flag,plugin)
        builder=(JAVA/"mixin/FunctionBuilderMixin.java").read_text()
        self.assertLess(builder.index("if (!ProbeConfiguration.wrapperEnabled())"),builder.index("ProbeMetrics.functionLoaded"))
if __name__=="__main__":unittest.main()
