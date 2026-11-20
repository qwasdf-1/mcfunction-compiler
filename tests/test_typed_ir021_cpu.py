"""IR-021 original SHA-pinned selector-fork stage CPU research safety contracts."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir021_cpu as ir

def fake(mode):
    result={}
    for kind,stride in ir.STREAMS.items():
        if kind=="modifier_other":
            count=0
        elif kind in ("exact_build_contexts","modifier_execute_as",
                      "entity_selector_find","continuation_initial_schedule"):
            count=1248
        else:
            count=327680
        samples=0 if mode=="plain" else count//stride
        raw=0 if mode=="plain" else samples*(900 if mode=="empty" else 1100)
        outputs=(count if kind in ("modifier_execute_as","modifier_score_predicate",
                      "entity_selector_find","continuation_initial_schedule") else 0)
        result[kind]={"stride":stride,"visits":count,"samples":samples,
                      "cpu_ns":raw,"invalid":0,"outputs":outputs,
                      "max_outputs": min(count,256) if outputs else 0}
    return {"cpu_rows":result,"server_thread_cpu":{
        "cpu_measurement_valid":True,
        "server_thread_cpu_running_ns":8_000_000_000}}

class IR021Contracts(unittest.TestCase):
    def test_pinned_exact_source_and_original_nested_methods(self):
        code=(ROOT/"src/main/java/dev/functioncompiler/CompilerForkBreakdownProbe.java").read_text()
        runner=(ROOT/"scripts/ci_typed_ir021_cpu.py").read_text()
        self.assertIn("erb:restore/job_tick",runner)
        self.assertIn("data/erb/function/restore/job_tick.mcfunction",runner)
        for token in ("erb.block","erb.verified","#active erb.job",
                      "#needs_restore erb.tmp 1"):
            self.assertIn(token,code)
            self.assertIn(token,runner)
        for token in ('"FC_CPU021_MODE"','"FC_CPU021_NAMESPACE"',
                      '"erb".equals(NAMESPACE)',
                      '"plain".equals(MODE)','"empty".equals(MODE)',
                      '"timed".equals(MODE)',
                      'if (!ACTIVE || !CONFIGURED || !ORIGINAL.equals(input)) return;',
                      'continuationConstructedForTarget()',
                      'continuationStepStart(boolean marked)',
                      'original.run(context)'):
            if token=='original.run(context)':
                # Original parser's terminal remains unmodified by this probe.
                self.assertNotIn("setCommand(",code)
            else:
                self.assertIn(token,code)
        self.assertNotIn('incrementCost()',code)
        self.assertNotIn('queueNext(',code)
        self.assertNotIn('ci.cancel()',code)

    def test_method_targets_are_exact_and_native(self):
        registry=(ROOT/"src/main/resources/function_compiler.mixins.json").read_text()
        for mix in ("CompilerForkContextChainMixin",
                    "CompilerForkEntitySelectorMixin",
                    "CompilerForkSourceMixin",
                    "CompilerForkContinuationMixin"):
            self.assertIn(mix,registry)
        cmd=(ROOT/"src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        self.assertEqual(cmd.count('Commands.literal("cpu021-start")'),2)
        self.assertEqual(cmd.count('Commands.literal("cpu021-stop")'),2)
        build=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerQueueBuildCpuMixin.java").read_text()
        self.assertIn("CompilerForkBreakdownProbe.buildStart(commandInput)",build)
        self.assertIn("CompilerForkBreakdownProbe.buildEnd(commandInput)",build)
        chain=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerForkContextChainMixin.java").read_text()
        self.assertIn('runModifier(Lcom/mojang/brigadier/context/CommandContext;',chain)
        self.assertIn("CompilerForkBreakdownProbe.modifierStart(context);",chain)
        self.assertIn("CompilerForkBreakdownProbe.modifierEnd(ci.getReturnValue());",chain)
        selector=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerForkEntitySelectorMixin.java").read_text()
        self.assertIn("findEntities(Lnet/minecraft/commands/CommandSourceStack;)",selector)
        source=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerForkSourceMixin.java").read_text()
        self.assertIn("withEntity(Lnet/minecraft/world/entity/Entity;)",source)
        cont=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerForkContinuationMixin.java").read_text()
        self.assertIn("ContinuationTask$TaskProvider;",cont)
        self.assertIn("continuationConstructedForTarget()",cont)
        self.assertIn("continuationStepEnd(",cont)

    def test_clock_matrices_and_nonadditive_stages(self):
        self.assertEqual(ir.MODES,("plain","empty","timed"))
        self.assertEqual(ir.WINDOW_SECONDS,30)
        self.assertEqual(len(ir.STREAMS),8)
        self.assertEqual(ir.STREAMS["exact_build_contexts"],16)
        self.assertEqual(ir.STREAMS["continuation_deferred_step"],128)
        arms={x:fake(x) for x in ir.MODES}
        report=ir.analysis(arms)
        self.assertFalse(report["causal_speedup_claim"])
        self.assertTrue(report["no_disjoint_summation"])
        self.assertTrue(report["rows"]["modifier_other"]["not_observed"])
        for label,row in report["rows"].items():
            if label=="modifier_other":continue
            self.assertEqual(row["signed_subtracted_ns_per_call"],200)
            self.assertFalse(row["exclusive_or_removable_cpu_claim"])
        bad=copy.deepcopy(arms)
        bad["timed"]["cpu_rows"]["source_with_entity"]["visits"]=600
        with self.assertRaises(AssertionError):
            ir.analysis(bad)

    def test_log_parser_rejects_lost_samples(self):
        def fixture(mode):
            lines=["FC_CPU021_BEGIN mode="+mode]
            for name,stride in ir.STREAMS.items():
                count=0 if name=="modifier_other" else (
                    1248 if stride==16 else 328000)
                samples=0 if mode=="plain" else count//stride
                val=0 if mode=="plain" else samples*700
                outputs=count if name in ("modifier_execute_as","modifier_score_predicate",
                                          "entity_selector_find",
                                          "continuation_initial_schedule") else 0
                lines.append(
                    f"FC_CPU021_ROW kind={name} stride={stride} visits={count} "
                    f"samples={samples} cpu_ns={val} invalid=0 "
                    f"outputs={outputs} max_outputs={min(outputs,256)}")
            return "\n".join(lines+["FC_CPU021_END mode="+mode])
        sample=fixture("empty")
        result=ir.parse_cpu021(sample,"empty")
        self.assertEqual(len(result),8)
        self.assertEqual(result["modifier_other"]["samples"],0)
        with self.assertRaises(AssertionError):
            ir.parse_cpu021(sample.replace("invalid=0","invalid=1",1),"empty")
        with self.assertRaises(AssertionError):
            ir.parse_cpu021(sample.replace("samples=78","samples=77",1),"empty")
        with self.assertRaises(AssertionError):
            ir.parse_cpu021(sample.replace("FC_CPU021_END mode=empty",""),"empty")
        with self.assertRaises(AssertionError):
            ir.parse_cpu021(fixture("plain").replace("cpu_ns=0","cpu_ns=22",1),"plain")

    def test_publisher_fixture_and_no_rewritten_scheduler_or_cpu_claim(self):
        runner=(ROOT/"scripts/ci_typed_ir021_cpu.py").read_text()
        setup=(ROOT/"scripts/ci_typed_ir019_blastback.py").read_text()
        for token in ('setup(cpu_mode=mode,output=output,cpu_family="021")',
                      'find_server_thread(proc.pid)','event_cpu_delta(',
                      '"full_restoration_claim":False',
                      '"new_compiled_opcode":False',
                      '"causal_speedup_claim":False',
                      "time.sleep(WINDOW_SECONDS)", "cpu021-start", "cpu021-stop"):
            self.assertIn(token,runner)
        for token in ('env["FC_CPU021_MODE"] = cpu_mode',
                      'env["FC_CPU021_NAMESPACE"] = "erb"',
                      'env["FC_COMPILER_EXEC_CENSUS"] = "false"'):
            self.assertIn(token,setup)

if __name__=="__main__":
    unittest.main()
