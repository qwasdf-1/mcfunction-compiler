"""IR-016 source-spanned mixed IR static contracts; native JVM tests are definitive."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir016 as study


def java(name: str) -> str:
    return (ROOT / "src/main/java/dev/functioncompiler" / name).read_text()


class IR016MixedProgramContracts(unittest.TestCase):
    def test_source_positioned_typed_and_original_barriers(self):
        src = java("MixedFunctionIR.java")
        for token in (
            "sealed interface Node permits TypedRegion, OpaqueBarrier",
            "record TypedRegion(", "record OpaqueBarrier(",
            "enum BarrierKind { UNSUPPORTED_OR_CONTROL, FUNCTION_DISPATCH, TYPED_SINGLETON }",
            "record Program(", "firstSourceIndex()", "sourceCount()",
            "node.firstSourceIndex() != expected", "expected != sourceCount",
            "pending.getFirst().vanilla().original()",
            "nodes.add(new OpaqueBarrier(index, entry,",
            "nodes.add(new TypedRegion(first, typed, emitted.action(), emitted.bytecode()))",
            "isFunctionDispatch(entry) ? BarrierKind.FUNCTION_DISPATCH",
        ):
            self.assertIn(token, src)
        self.assertIn("directBytecodeChunks()", src)
        self.assertIn("!t.bytecode()", src)
        self.assertIn("typedSourceCount() != sourceCount", src)

    def test_compiler_uses_mixed_program_as_only_lowering(self):
        compiler = java("TypedScoreIR.java")
        self.assertIn("MixedFunctionIR.Program mixed = MixedFunctionIR.lower(original)", compiler)
        self.assertIn("mixed.executableEntries()", compiler)
        self.assertIn("mixed.directBytecodeChunks()", compiler)
        self.assertIn("MixedFunctionIR.diagnostics()", compiler)
        self.assertIn("static EmittedRegion emitRegion(Program program)", compiler)
        self.assertNotIn("private static boolean flush(", compiler)

    def test_diagnostics_bound_and_harness_gated(self):
        ir = java("MixedFunctionIR.java")
        commands = java("ProbeCommands.java")
        self.assertIn('System.getenv("FC_TYPED_IR_DIAGNOSTICS")', ir)
        self.assertIn("MAX_LEDGER_FUNCTIONS = 2048", ir)
        self.assertIn("MAX_LAYOUT_NODES = 24", ir)
        self.assertIn('Commands.literal("ir016")', commands)
        self.assertIn('Commands.literal("fc_ir016_call")', commands)
        self.assertIn('System.getenv("FC_TYPED_IR_MIXED_TEST_HARNESS")', commands)
        self.assertIn('id.getPath().matches("ir016_[a-z0-9_]+")', commands)
        self.assertIn('id.getPath().matches("ir01[34]_[a-z0-9_]+")', commands)

    def test_native_fixture_original_source_and_expected_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            study.fixture(Path(tmp))
            funcs=Path(tmp)/"world/datapacks"/study.PACK/"data/fc_ir/function"
            for name, lines in study.FUNCTIONS.items():
                self.assertEqual((funcs/(name+".mcfunction")).read_text().splitlines(), lines)
        self.assertEqual(study.EXPECTED["ir016_call_chain"]["x"], 36)
        self.assertEqual(study.EXPECTED["ir016_return"]["x"], 3)
        self.assertEqual(study.EXPECTED["ir016_store"]["stored"], 7)
        self.assertEqual(study.EXPECTED["ir016_modded"]["stored"], 7)
        self.assertEqual(len(study.FUNCTIONS["ir016_chunk65"]), 65)
        self.assertEqual(len(study.FUNCTIONS["ir016_chunk66"]), 66)
        self.assertIn(1, study.QUOTAS)
        self.assertIn(65, study.QUOTAS)

    def test_four_modes_and_no_production_flags(self):
        self.assertEqual(study.MODES,
                         ("native", "interpreted", "bytecode", "bytecode_direct"))
        for mode in study.MODES[1:]:
            flags=study.options(mode)
            self.assertEqual(flags["FC_TYPED_IR_NAMESPACE"], "fc_ir")
            self.assertEqual(flags["FC_TYPED_IR_REENTRANT_SAFE"], "true")
            self.assertEqual(flags["FC_TYPED_IR_MIXED_TEST_HARNESS"], "true")
            for disabled in ("FC_SCORE_ADD_PROTOTYPE", "FC_FUSED_REGION_PROTOTYPE",
                             "FC_BYTECODE_REGION_PROTOTYPE", "FC_TYPED_IR_SCORE_CACHE",
                             "FC_TYPED_IR_SINGLETON_FEEDBACK"):
                self.assertEqual(flags[disabled], "false")
        self.assertEqual(study.options("native")["FC_WRAPPER_PROBE"], "false")
        script=(ROOT/"scripts/ci_typed_ir016.py").read_text()
        for token in ("native_semantic_parity", "performance_claim",
                      "production_promotion", "source_lines", "opaque_barriers",
                      "direct_candidate", "snapshot(client)", "CASES"):
            self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
