"""IR025 compiler-generated native-selector fork safety and source contracts."""
from pathlib import Path
import sys
import unittest
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir025_compiled_fork as f

def src(name:str)->str:
    return (ROOT/"src/main/java/dev/functioncompiler"/name).read_text()

class IR025ForkCompilerContracts(unittest.TestCase):
    def test_generated_jvm_action_really_replaces_original_fork_entry(self):
        emitter=src("CompilerForkBytecode025.java")
        mixed=src("MixedFunctionIR.java")
        for term in (
            "ClassWriter.COMPUTE_FRAMES","defineHiddenClass(",
            "visitMethodInsn(INVOKESTATIC, RUNTIME, \"run\"",
            "new String[]{ACTION}","CompilerForkPlan024.Plan.class",
            "UnboundEntryAction.class",
        ):
            self.assertIn(term,emitter)
        for term in (
            "CompilerForkExecutor025.compile(plan, entry)",
            "nodes.add(new NativeForkPlanBarrier(",
            "index, plan, generated, true",
            "node instanceof NativeForkPlanBarrier f",
            '(f.bytecode() ? "C" : "N")',
            '" compiled_forks=" + compiledForkCount()',
            "nodes.add(new NativeForkPlanBarrier(index, plan, entry))",
            "nodes.stream().anyMatch(n -> !(n instanceof TypedRegion t)",
        ):
            self.assertIn(term,mixed)

    def test_runtime_calls_original_selector_native_continuation_and_terminal(self):
        runtime=src("CompilerForkExecutor025.java")
        plan=src("CompilerForkPlan024.java")
        for term in (
            "plan.nativeSelector().findEntities(source)",
            "candidates.add(source.withEntity(entity))",
            "board.getPlayerScoreInfo(entity, entityObjective)",
            "ScoreHolder.forNameOnly(plan.comparisonHolder())",
            "new ExecuteCommand<>(",
            "ChainModifiers.DEFAULT.setForked()",
            "ContinuationTask.schedule(context, frame, passing,",
            "originalTerminal.bind(entitySource)",
            "context.incrementCost()",
            "BuildContexts.ERROR_FORK_LIMIT_REACHED",
            "source.handleError(",
            "original.execute(source, context, frame)",
            "context.profiler().pop()",
            "MIN_FAST_QUOTA = 1024",
            'System.getenv("FC_TYPED_IR_COMPILED_FORK")',
        ):
            self.assertIn(term,runtime)
        for token in (
            "String commandInput","CommandContext<CommandSourceStack> terminalContext",
            "as.getArgument(\"targets\", EntitySelector.class)",
            "as.getRedirectModifier() == null",
            "condition.getRedirectModifier() == null",
            "ScoreAddPrototype.extractNodeText(",
        ):
            self.assertIn(token,plan)
        for forbidden in (
            "new EntitySelector(","CachedMembership","HashMap<",
            "ConcurrentHashMap<","WeakHashMap<","entityTags().add(",
            "entityTags().remove(","world.getEntities().forEach",
            "ContextChain.runModifier(", "ContextChain.runExecutable(",
            "new ContinuationTask",
        ):
            self.assertNotIn(forbidden,runtime+emitter)

    def test_original_fixtures_include_native_deferred_and_guard_edges(self):
        self.assertEqual(f.MODES,("native","plan_only","compiled"))
        self.assertEqual(len(f.CASES),len(f.base.EXPECTED)+len(f.ADDED))
        self.assertIn(1,f.QUOTAS)
        self.assertIn(1024,f.QUOTAS)
        self.assertIn("multi_four",f.ADDED)
        self.assertEqual(sum("summon minecraft:marker" in line
                             for line in f.ADDED["multi_four"]),4)
        self.assertEqual(sum("summon minecraft:marker" in line
                             for line in f.ADDED["partial"]),4)
        self.assertIn("sort=nearest,limit=1",f.SORTED)
        for name in ("no_candidate","multi_four","partial","sorted_first_fails",
                     "missing_guard_objective","missing_terminal_objective"):
            self.assertIn(name,f.EXPECTED)
        self.assertEqual(f.EXPECTED["multi_four"]["#steps"],5)
        self.assertEqual(f.EXPECTED["sorted_first_fails"]["#sorted"],0)
        self.assertIn(f.HOT("hit"),f.base.FUNCTIONS["plan_case"])
        with tempfile.TemporaryDirectory() as tmp:
            f.configure_base()
            f.base.fixture(Path(tmp))
            funcs=Path(tmp)/"world/datapacks"/f.base.PACK/"data/fc_ir024/function"
            for name,lines in f.ADDED.items():
                self.assertEqual((funcs/(name+".mcfunction")).read_text().splitlines(),lines)

    def test_flags_disabled_by_default_no_external_index(self):
        for mode in f.MODES:
            env=f.options(mode)
            self.assertEqual(env["FC_TYPED_IR_COMPILED_FORK"],
                             str(mode=="compiled").lower())
            self.assertEqual(env["FC_TYPED_IR_NATIVE_FORK_PLAN"],
                             str(mode!="native").lower())
            self.assertEqual(env["FC_TYPED_IR_SCORE_CACHE"],"false")
            self.assertEqual(env["FC_TYPED_IR_DIRECT_FUNCTION"],"false")
            self.assertEqual(env["FC_IR023_VISIBILITY_HARNESS"],"false")
        text=(ROOT/"scripts/ci_typed_ir025_compiled_fork.py").read_text()
        for label in ("native_semantic_parity","compiled_fork_execution_proven",
                      "native_terminal_and_continuation_preserved",
                      "global_entity_index","snapshots_per_arm"):
            self.assertIn(label,text)

if __name__=="__main__":
    unittest.main()
