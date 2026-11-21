"""IR-010 source/effect and deterministic native fixture contracts."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir010 as ir


class TypedIR010(unittest.TestCase):
    def test_fixture_expected_states_and_original_source(self):
        with tempfile.TemporaryDirectory() as work:
            ir.make_pack(Path(work))
            root = Path(work) / "world/datapacks/fc_typed_ir_010/data/fc_ir/function"
            for name in ir.EXPECTED:
                file = root / f"{name}.mcfunction"
                self.assertTrue(file.exists(), name)
                self.assertEqual(file.read_text().splitlines(), ir.CASES[name])
        self.assertEqual(len(ir.CASES["bench64"]), 64)
        self.assertEqual(sum("operation " in x for x in ir.CASES["bench64"]), 62)
        self.assertEqual(ir.EXPECTED["bench64"]["a"], 434)

    def test_mutations_cross_binary_reads_with_synch_callback_and_reset(self):
        observer = ir.CASES["observer_invalidated"]
        self.assertLess(next(i for i, x in enumerate(observer) if "operation " in x),
                        next(i for i, x in enumerate(observer) if "#fc_ir010_trigger" in x))
        self.assertGreater(sum("operation " in x for x in observer), 1)
        reset = ir.CASES["reset_invalidated"]
        self.assertTrue(any("#fc_ir010_reset" in x for x in reset))
        self.assertIn("write_invalidated", ir.EXPECTED)
        self.assertIn("alias_write", ir.EXPECTED)
        self.assertIn("barrier", ir.EXPECTED)

    def test_cache_compilation_switch_is_not_production_default(self):
        irsrc = (ROOT / "src/main/java/dev/functioncompiler/TypedScoreIR.java").read_text()
        runtime = (ROOT / "src/main/java/dev/functioncompiler/TypedScoreIRRuntime.java").read_text()
        asm = (ROOT / "src/main/java/dev/functioncompiler/TypedScoreIRBytecode.java").read_text()
        self.assertIn('System.getenv("FC_TYPED_IR_SCORE_CACHE")', irsrc)
        self.assertIn('System.getenv("FC_TYPED_IR_SCORE_CACHE_TOGGLE")', irsrc)
        self.assertIn("private static volatile boolean scoreCacheRuntime", irsrc)
        self.assertIn('method.visitMethodInsn(INVOKEVIRTUAL, STATE, "sourceOperand"', asm)
        self.assertIn('if (TypedScoreIR.scoreCacheCompiled())', asm)
        self.assertIn("cachedSources", runtime)
        self.assertIn("entry.revision() == revision", runtime)
        self.assertIn("entry.objective() == sourceObjective", runtime)
        self.assertIn("sourceAccess.get()", runtime)
        self.assertIn("getOrCreatePlayerScore", runtime)
        self.assertIn("FusedRegionPrototype.executeCommand", runtime)

    def test_invalidation_mixin_covers_changes_and_removals(self):
        path = ROOT / "src/main/java/dev/functioncompiler/mixin/ScoreValueRevisionMixin.java"
        src = path.read_text()
        for term in ('method = "onScoreChanged"',
                     'method = "onPlayerRemoved"',
                     'method = "onPlayerScoreRemoved"',
                     'method = "onObjectiveRemoved"',
                     'functionCompiler$bumpByHolder',
                     'functionCompiler$bumpByObjective',
                     'FC_TYPED_IR_SCORE_CACHE_TEST_OBSERVER',
                     '#fc_ir010_trigger', '#fc_ir010_reset'):
            self.assertIn(term, src)
        config = (ROOT / "src/main/resources/function_compiler.mixins.json").read_text()
        self.assertIn('"ScoreValueRevisionMixin"', config)

    def test_crossover_balancing_and_exact_same_function(self):
        self.assertEqual(ir.BOOTS, 2)
        for boot in range(ir.BOOTS):
            rows = ir.plan(boot)
            self.assertEqual(len(rows), ir.BLOCKS_PER_BOOT + ir.AA_PER_BOOT)
            self.assertEqual(sum(x["kind"] == "cache_vs_off" for x in rows),
                             ir.BLOCKS_PER_BOOT)
            self.assertEqual(sum(x["kind"] == "off_aa" for x in rows), ir.AA_PER_BOOT)
            self.assertEqual(sum(x["order"] == "ABBA" for x in rows if
                                 x["kind"] == "cache_vs_off"), ir.BLOCKS_PER_BOOT // 2)
        self.assertIn('invoke(client, "bench64")',
                      (ROOT / "scripts/ci_typed_ir010.py").read_text())
        self.assertTrue(ir.options("bytecode_cache")["FC_TYPED_IR_SCORE_CACHE"] == "true")
        self.assertTrue(ir.options("bytecode_off")["FC_TYPED_IR_SCORE_CACHE"] == "false")
        self.assertTrue(ir.options("native")["FC_TYPED_IR_SCORE_CACHE_TEST_OBSERVER"] == "true")
        self.assertTrue(ir.options("bytecode_cache", crossover=True)["FC_TYPED_IR_SCORE_CACHE_TOGGLE"] == "true")

    def test_research_toggle_is_explicit_and_does_not_change_bytecode(self):
        commands = (ROOT / "src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        self.assertIn('System.getenv("FC_TYPED_IR_SCORE_CACHE_TOGGLE")', commands)
        self.assertIn('Commands.literal("fc_ir010_cache")', commands)
        self.assertIn("TypedScoreIR.toggleCache", commands)
        script = (ROOT / "scripts/ci_typed_ir010.py").read_text()
        self.assertIn("fc_ir010_cache ", script)
        self.assertIn('"off_aa"', script)
        self.assertIn('"causal_general_speedup": False', script)
        self.assertIn('"production_promotion": False', script)


if __name__ == "__main__":
    unittest.main()
