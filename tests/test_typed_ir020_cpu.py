"""COMPILER-IR-020: source-pinned transparent fork/leaf CPU diagnostic contracts."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir020_cpu as cpu


def fake_arm(mode:str, build=1240, execute=318000, leaf=318000):
    rows={}
    for key,stride in cpu.STREAMS.items():
        visits=build if key=="restore_selector_build" else (
            execute if key=="restore_terminal_execute" else leaf)
        n=visits//stride if mode!="plain" else 0
        # Make empty clock read more expensive in a purposefully negative
        # example to protect signed value reporting; never clamp to zero.
        interval=0 if mode=="plain" else (1100 if mode=="empty" else 900)
        rows[key]={"stride":stride,"visits":visits,"samples":n,
                   "cpu_ns":n*interval,"invalid":0}
    return {
        "mode":mode,"cpu_rows":rows,
        "server_thread_cpu":{"cpu_measurement_valid":True,
                             "server_thread_cpu_running_ns":8_000_000_000},
    }


class RestoreCpuProbeContracts(unittest.TestCase):
    def test_exact_original_source_binds_cpu_probe_to_unique_restore_site(self):
        original=(ROOT/"scripts/ci_typed_ir020_cpu.py").read_text()
        java=(ROOT/"src/main/java/dev/functioncompiler/CompilerRestoreCpuProbe.java").read_text()
        self.assertIn('data/erb/function/restore/job_tick.mcfunction',original)
        self.assertIn('lines[4]!=EXACT_ORIGINAL_LINE',original)
        self.assertIn('lines.count(EXACT_ORIGINAL_LINE)!=1',original)
        self.assertIn('"erb:restore/job_tick"',java)
        self.assertIn("if (found != 1)",java)
        self.assertIn('ORIGINAL_COMMAND.equals(input)',java)
        for term in ("erb.block","erb.verified","if score @s erb.job",
                     "#needs_restore erb.tmp 1"):
            self.assertIn(term,java)
            self.assertIn(term,cpu.EXACT_ORIGINAL_LINE)

    def test_research_is_off_by_default_and_original_semantics_remain(self):
        java=(ROOT/"src/main/java/dev/functioncompiler/CompilerRestoreCpuProbe.java").read_text()
        wrapper=(ROOT/"src/main/java/dev/functioncompiler/ProbeFunctionWrapper.java").read_text()
        probe=(ROOT/"src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        build=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerQueueBuildCpuMixin.java").read_text()
        execute=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerQueueExecuteCpuMixin.java").read_text()
        for t in ('"FC_CPU020_MODE"','"FC_CPU020_NAMESPACE"',
                  '"erb".equals(NAMESPACE)','"plain".equals(MODE)',
                  '"empty".equals(MODE)','"timed".equals(MODE)',
                  'if (!ACTIVE || kind < 0) return -1L;',
                  'return original.run(context);','new TimedLeaf<>(callback)'):
            self.assertIn(t,java)
        self.assertIn('CompilerRestoreCpuProbe.instrument(',wrapper)
        self.assertIn('return restoreCpuPlainInstantiation;',wrapper)
        self.assertEqual(probe.count('Commands.literal("cpu020-start")'),2)
        self.assertEqual(probe.count('Commands.literal("cpu020-stop")'),2)
        self.assertIn("CompilerRestoreCpuProbe.beginBuild(commandInput)",build)
        self.assertIn("CompilerRestoreCpuProbe.endBuild(commandInput",build)
        self.assertIn("CompilerRestoreCpuProbe.beginExecute(commandInput)",execute)
        self.assertIn("CompilerRestoreCpuProbe.endExecute(commandInput",execute)
        self.assertNotIn("ci.cancel()",java)
        self.assertNotIn("queueNext(",java)

    def test_original_native_three_arm_calibration_and_overlap_guards(self):
        self.assertEqual(cpu.MODES,("plain","empty","timed"))
        self.assertEqual(cpu.WINDOW_SECONDS,30)
        self.assertEqual(set(cpu.STREAMS),{
            "restore_selector_build","restore_terminal_execute",
            "restore_scoreboard_leaf"})
        self.assertEqual(cpu.STREAMS["restore_selector_build"],16)
        self.assertEqual(cpu.STREAMS["restore_terminal_execute"],128)
        self.assertEqual(cpu.STREAMS["restore_scoreboard_leaf"],128)
        arms={mode:fake_arm(mode) for mode in cpu.MODES}
        result=cpu.analysis(arms)
        self.assertFalse(result["causal_speedup_claim"])
        self.assertTrue(result["no_disjoint_summation"])
        self.assertFalse(result["same_original_gameplay_or_restoration_completion"])
        for row in result["rows"].values():
            self.assertLess(row["signed_subtracted_ns_per_call"],0)
            self.assertLess(row["signed_fraction_of_timed_server_cpu"],0)
            self.assertFalse(row["exclusive_or_removable_cpu_claim"])
        bad=copy.deepcopy(arms)
        bad["empty"]["cpu_rows"]["restore_scoreboard_leaf"]["visits"]=5
        with self.assertRaises(AssertionError):
            cpu.analysis(bad)

    def test_native_sample_parser_rejects_missing_and_overflow(self):
        def raw(mode):
            lines=["FC_CPU020_BEGIN mode="+mode]
            for name,stride in cpu.STREAMS.items():
                n=1248 if name=="restore_selector_build" else 318080
                sample=n//stride if mode!="plain" else 0
                lines.append(
                    "FC_CPU020_ROW kind="+name+f" stride={stride} visits={n} "
                    f"samples={sample} cpu_ns={sample*1000} invalid=0")
            lines.append("FC_CPU020_END mode="+mode)
            return "\n".join(lines).replace(
                "cpu_ns=0 invalid=0","cpu_ns=0 invalid=0")
        text=raw("timed")
        rows=cpu.parse_cpu020(text,"timed")
        self.assertEqual(rows["restore_selector_build"]["samples"],78)
        with self.assertRaises(AssertionError):
            cpu.parse_cpu020(text.replace("invalid=0","invalid=1",1),"timed")
        with self.assertRaises(AssertionError):
            cpu.parse_cpu020(text.replace("samples=78","samples=77",1),"timed")
        with self.assertRaises(AssertionError):
            cpu.parse_cpu020(text.replace("FC_CPU020_END mode=timed",""),"timed")
        with self.assertRaises(AssertionError):
            cpu.parse_cpu020(raw("plain").replace("cpu_ns=0","cpu_ns=50",1),"plain")

    def test_three_native_arms_do_not_compile_or_claim_restoration(self):
        runner=(ROOT/"scripts/ci_typed_ir020_cpu.py").read_text()
        ir019=(ROOT/"scripts/ci_typed_ir019_blastback.py").read_text()
        for term in (
            'setup(cpu_mode=mode,output=output)',
            'find_server_thread(proc.pid)', 'read_thread_schedstat(',
            'event_cpu_delta(', "cpu020-start", "cpu020-stop",
            'Fuse:160s','tag=fc_blastback_probe',
            '"full_restoration_claim":False',
            '"causal_speedup_claim":False',
            '"new_compiled_opcode":False',
            "time.sleep(WINDOW_SECONDS)",
        ):
            self.assertIn(term,runner)
        for term in ('"FC_COMPILER_EXEC_CENSUS"] = "false"',
                     'env["FC_CPU020_MODE"] = cpu_mode',
                     'env["FC_CPU020_NAMESPACE"] = "erb"'):
            self.assertIn(term,ir019)


if __name__=="__main__":
    unittest.main()
