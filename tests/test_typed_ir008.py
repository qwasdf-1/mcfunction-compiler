"""IR-008 research contract: typed source, safe fallbacks, strict native parity gate."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir008 as ir


class TypedIr008(unittest.TestCase):
    def test_explicit_opt_in_only(self):
        for mode in ir.MODES:
            env = ir.options(mode)
            self.assertEqual(env["FC_TYPED_IR_MODE"],
                             mode if mode in ("interpreted", "bytecode") else "")
            self.assertEqual(env["FC_TYPED_IR_NAMESPACE"],
                             ir.NS if mode in ("interpreted", "bytecode") else "")
            self.assertEqual(env["FC_BYTECODE_REGION_PROTOTYPE"], "false")
            self.assertEqual(env["FC_COMMAND_CALLBACK_METRICS"], "false")

    def test_fixture_has_multiple_dependent_mutations_and_real_barriers(self):
        self.assertGreaterEqual(len(ir.FUNCTIONS["chain"]), 4)
        self.assertIn("function fc_ir:helper", ir.FUNCTIONS["barrier"])
        self.assertTrue(any("execute if score" in c for c in ir.FUNCTIONS["conditional"]))
        self.assertTrue(any("scoreboard players operation" in c for c in ir.FUNCTIONS["operation"]))
        self.assertEqual(len(ir.FUNCTIONS["bench64"]), ir.BENCH_OPS)
        self.assertEqual(ir.BENCH_OPS, 64)

    def test_native_fixture_generates_publisher_independent_pack(self):
        with tempfile.TemporaryDirectory() as directory:
            ir.fixture(Path(directory))
            root = Path(directory) / "world/datapacks" / ir.PACK
            self.assertTrue((root / "pack.mcmeta").exists())
            path = root / "data/fc_ir/function/conditional.mcfunction"
            self.assertEqual(
                path.read_text().splitlines(),
                ir.FUNCTIONS["conditional"]
            )

    def test_parity_rejects_missing_arm(self):
        with self.assertRaisesRegex(ValueError, "four independent"):
            ir.validate([{"mode": "native", "status": "accepted"}])

    def test_parity_rejects_divergence_even_if_all_arms_accepted(self):
        cases = {"x": 13}
        rows = [{
            "mode": mode,
            "status": "accepted", "semantic_verified": True,
            "cases": cases if mode != "bytecode" else {"x": 12},
            "screen": {"expected_writes": ir.BENCH_CALLS * ir.BENCH_OPS,
                       "linux_server_thread_cpu_ns": 12345},
        } for mode in ir.MODES]
        with self.assertRaisesRegex(AssertionError, "parity mismatch"):
            ir.validate(rows)

    def test_parity_is_noncausal_by_contract(self):
        rows = [{
            "mode": mode,
            "status": "accepted", "semantic_verified": True,
            "cases": {"x": 13},
            "screen": {"expected_writes": ir.BENCH_CALLS * ir.BENCH_OPS,
                       "linux_server_thread_cpu_ns": 12345},
        } for mode in ir.MODES]
        result = ir.validate(rows)
        self.assertTrue(result["native_parity"])
        self.assertFalse(result["causal_speedup_established"])
        self.assertFalse(result["compiler_production_promotion"])

    def test_generated_backend_must_not_delegate_each_step(self):
        source = (ROOT / "src/main/java/dev/functioncompiler/TypedScoreIRBytecode.java"
                  ).read_text(encoding="utf-8")
        self.assertIn('INVOKEINTERFACE, SCORE, "add"', source)
        self.assertIn('INVOKEINTERFACE, SCORE, "set"', source)
        self.assertNotIn('"executeStep"', source)
        self.assertNotIn('"runExecutable"', source)

    def test_runtime_preserves_observable_score_per_command(self):
        source = (ROOT / "src/main/java/dev/functioncompiler/TypedScoreIRRuntime.java"
                  ).read_text(encoding="utf-8")
        for expected in ("context.incrementCost()", "tracer.onCommand",
                         "tracer.onReturn", "getOrCreatePlayerScore",
                         "response.sendFeedback", "FusedRegionPrototype.executeCommand"):
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
