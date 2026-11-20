"""IR-014 static acceptance contracts; only a native server run proves parity."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir014 as study


class CompilerIR014(unittest.TestCase):
    def test_test_only_callback_routes_nested_and_objective_lifecycle(self):
        probe = (ROOT / "src/main/java/dev/functioncompiler/ReentrantQueueProbe.java").read_text()
        for holder, destination in (
            ("#ir014_chain", "ir014_inject_first"),
            ("#ir014_second", "ir014_inject_second"),
            ("#ir014_recreate", "ir014_inject_recreate"),
            ("#ir014_drop", "ir014_inject_drop"),
            ("#ir014_return", "ir014_inject_return"),
        ):
            self.assertIn(holder, probe)
            self.assertIn(destination, probe)
        self.assertIn("ExecutionContext.queueInitialFunctionCall(", probe)
        self.assertIn('System.getenv("FC_TYPED_IR_REENTRANT_TEST_OBSERVER")', probe)
        self.assertIn("ExecutionContextBridge.currentContext()", probe)
        commands = (ROOT / "src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        self.assertIn('id.getPath().matches("ir01[34]_[a-z0-9_]+")', commands)

    def test_real_multi_level_interleaving_and_identity_fixtures(self):
        self.assertIn("scoreboard players set #ir014_second fc_ir 1",
                      study.FUNCTIONS["ir014_inject_first"])
        self.assertIn("scoreboard players operation #ir014_inner_seen fc_ir = "
                      "#ir014_marker fc_ir",
                      study.FUNCTIONS["ir014_inject_first"])
        self.assertIn("scoreboard players add #ir014_marker fc_ir 9",
                      study.FUNCTIONS["ir014_inject_second"])
        self.assertEqual(study.EXPECTED["ir014_cascade"]["inner_seen"], 9)
        self.assertEqual(study.EXPECTED["ir014_cascade"]["seen"], 11)
        self.assertIn("scoreboard objectives remove fc_aux",
                      study.FUNCTIONS["ir014_inject_recreate"])
        self.assertIn("scoreboard objectives add fc_aux dummy",
                      study.FUNCTIONS["ir014_inject_recreate"])
        self.assertIn("scoreboard objectives remove fc_aux",
                      study.FUNCTIONS["ir014_inject_drop"])
        self.assertEqual(study.FUNCTIONS["ir014_inject_return"][0], "return 0")
        self.assertIn("execute if score", study.FUNCTIONS["ir014_guarded"][1])

    def test_native_fixture_uses_original_function_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            study.fixture(Path(tmp))
            functions = (Path(tmp) / "world/datapacks" / study.PACK
                         / "data/fc_ir/function")
            for name, lines in study.FUNCTIONS.items():
                self.assertEqual(
                    (functions / f"{name}.mcfunction").read_text().splitlines(), lines)

    def test_guarded_native_variants_and_quota_matrix(self):
        self.assertEqual(study.MODES, ("native", "bytecode_guarded",
                                      "interpreted_guarded", "direct_guarded"))
        self.assertIn(1, study.QUOTAS)
        self.assertIn(65, study.QUOTAS)
        for mode in study.MODES[1:]:
            from ci_typed_ir013 import options
            self.assertEqual(options(mode)["FC_TYPED_IR_REENTRANT_SAFE"], "true")
            self.assertEqual(options(mode)["FC_TYPED_IR_REENTRANT_TEST_OBSERVER"], "true")
        script = (ROOT / "scripts/ci_typed_ir014.py").read_text()
        for token in ("native_semantic_parity", "reentrant_yields",
                      "reentrant_queued_steps", "direct_function_executed",
                      "aux_exists", "aux_input",
                      "production_promotion", "performance_claim"):
            self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
