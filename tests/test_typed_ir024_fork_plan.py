"""IR-024 compiler-owned native-fork plan admission; native JVM parity is definitive."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir024_fork_plan as ir


class IR024CompilerPlanContracts(unittest.TestCase):
    def test_immutable_native_selector_plan_is_compiler_owned(self):
        src=(ROOT/"src/main/java/dev/functioncompiler/CompilerForkPlan024.java").read_text()
        for required in (
            'System.getenv("FC_TYPED_IR_NATIVE_FORK_PLAN")',
            "record Plan(", "EntitySelector nativeSelector",
            "ContextChainAccessor<CommandSourceStack>",
            "stages.functionCompiler$getModifiers()",
            'as.getArgument("targets", EntitySelector.class)',
            "if (modifiers.size() != 3",
            'ScoreAddPrototype.nodeNames(modifiers.get(2)).equals(List.of("run"))',
            "terminalNodes.contains(\"set\")",
            "if (!ENABLED", "original instanceof BuildContexts.Unbound<?>",
        ):
            self.assertIn(required,src)
        for forbidden in ("selector.findEntities(","new EntitySelector(", "new HashMap",
                          "cachedMembership", "revisionMap", "queueNext(","setReturnValue("):
            self.assertNotIn(forbidden,src)

    def test_native_fork_remains_source_positioned_original_barrier(self):
        ir_src=(ROOT/"src/main/java/dev/functioncompiler/MixedFunctionIR.java").read_text()
        for required in (
            "sealed interface Node permits TypedRegion, OpaqueBarrier, NativeForkPlanBarrier",
            "record NativeForkPlanBarrier(",
            "CompilerForkPlan024.classify(entry)",
            "nodes.add(new NativeForkPlanBarrier(index, plan, entry))",
            "node instanceof NativeForkPlanBarrier f",
            '(f.bytecode() ? "C" : "N")',
            '" native_fork_plans=" + nativeForkPlanCount()',
            "n instanceof NativeForkPlanBarrier",
            "node instanceof TypedRegion t",  # direct BytecodeChunks whitelist
            "|| !t.bytecode()",
            "nodes.stream().anyMatch(n -> !(n instanceof TypedRegion t)",
        ):
            self.assertIn(required,ir_src)
        self.assertNotIn("CompilerForkPlan024.Plan plan = CompilerForkPlan024.classify(entry);\n                nodes.add(new TypedRegion",ir_src)
        runtime=(ROOT/"src/main/java/dev/functioncompiler/TypedScoreIR.java").read_text()
        self.assertIn("mixed.directBytecodeChunks()",runtime)
        self.assertIn("MixedFunctionIR.Program mixed = MixedFunctionIR.lower(original)",runtime)

    def test_native_original_world_fixture_and_order(self):
        self.assertEqual(ir.MODES,("native","fork_plan"))
        self.assertEqual(len(ir.FUNCTIONS["plan_case"]),14)
        self.assertEqual(sum("if score @s fc024" in x and "run scoreboard players set" in x
                             for x in ir.FUNCTIONS["plan_case"]),3)
        self.assertEqual(ir.FUNCTIONS["plan_case"][7],ir.HOT("hit"))
        self.assertEqual(ir.FUNCTIONS["plan_case"][10],ir.HOT("hit_after"))
        self.assertEqual(ir.FUNCTIONS["plan_case"][12],ir.HOT("hit_reenabled"))
        self.assertEqual(ir.EXPECTED["plan_case"],{
            "#active":7,"#hit":1,"#hit_after":0,
            "#hit_reenabled":1,"#steps":3})
        self.assertEqual(ir.EXPECTED["near_miss"],{"#miss":1,"#steps":1})
        self.assertIn(1,ir.QUOTAS)
        self.assertIn(64,ir.QUOTAS)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ir.fixture(root)
            folder=root/"world/datapacks"/ir.PACK/"data/fc_ir024/function"
            for name,commands in ir.FUNCTIONS.items():
                self.assertEqual((folder/(name+".mcfunction")).read_text().splitlines(),
                                 commands)
            pack=(root/"world/datapacks"/ir.PACK/"pack.mcmeta").read_text()
            self.assertIn('"min_format": [97, 1]',pack)
            self.assertIn('"max_format": [97, 1]',pack)

    def test_compile_mode_and_research_safety(self):
        original=ir.options("native")
        specialized=ir.options("fork_plan")
        self.assertEqual(original["FC_WRAPPER_PROBE"],"false")
        self.assertEqual(original["FC_TYPED_IR_MODE"],"")
        self.assertEqual(original["FC_TYPED_IR_NATIVE_FORK_PLAN"],"false")
        self.assertEqual(specialized["FC_TYPED_IR_MODE"],"bytecode")
        self.assertEqual(specialized["FC_TYPED_IR_NAMESPACE"],"fc_ir024")
        self.assertEqual(specialized["FC_TYPED_IR_NATIVE_FORK_PLAN"],"true")
        self.assertEqual(specialized["FC_TYPED_IR_DIRECT_FUNCTION"],"false")
        for flag in ("FC_TYPED_IR_SCORE_CACHE","FC_SCORE_ADD_PROTOTYPE",
                     "FC_FUSED_REGION_PROTOTYPE","FC_BYTECODE_REGION_PROTOTYPE",
                     "FC_IR023_VISIBILITY_HARNESS"):
            self.assertEqual(specialized[flag],"false")
        runner=(ROOT/"scripts/ci_typed_ir024_fork_plan.py").read_text()
        for word in ("native_semantic_parity","plan_admission_only",
                     "native_selector_execution","selector_replacement",
                     "native_fork_plans","native_fork_preserved",
                     "snapshots_per_arm","causal_cpu_claim"):
            self.assertIn(word,runner)


if __name__=="__main__":
    unittest.main()
