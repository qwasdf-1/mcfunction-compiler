"""IR-022 safety: exact source, native delegation, CONTROL and signed clocks."""
from pathlib import Path
import sys
import copy
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir022_cpu as ir

def arm(mode):
    rows={}
    for kind,stride in ir.STREAMS.items():
        if kind=="native_type_try_cast":
            visits=350080 if mode!="control" else 0
            passed=326016 if mode!="control" else 0
            output=0
        elif kind=="native_composite_predicate":
            visits=326016 if mode!="control" else 0
            passed=326016 if mode!="control" else 0
            output=0
        else:
            visits=1264
            passed=326016 if kind=="selector_sort_and_limit" else 0
            output=326016 if kind in (
                "selector_find_entire","selector_gather_entities",
                "selector_sort_and_limit") else 0
        samples=visits//stride if mode in ("empty","timed") else 0
        cpu=0 if mode in ("control","plain") else samples*(900 if mode=="empty" else 1200)
        rows[kind]={"stride":stride,"visits":visits,
                    "samples":samples,"cpu_ns":cpu,"invalid":0,
                    "passed":passed,"outputs":output,
                    "max_outputs":min(output,326016)}
    return {"cpu_rows":rows,
            "server_thread_cpu":{"cpu_measurement_valid":True,
                                 "server_thread_cpu_running_ns":7_000_000_000}}

class IR022Contracts(unittest.TestCase):
    def test_native_input_delegate_and_original_output_not_replaced(self):
        java=(ROOT/"src/main/java/dev/functioncompiler/CompilerSelector022Probe.java").read_text()
        mx=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerSelector022Mixin.java").read_text()
        commands=(ROOT/"src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        parent=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerQueueBuildCpuMixin.java").read_text()
        mixins=(ROOT/"src/main/resources/function_compiler.mixins.json").read_text()
        runner=(ROOT/"scripts/ci_typed_ir022_cpu.py").read_text()
        for needle in (
            '"FC_CPU022_MODE"','"FC_CPU022_NAMESPACE"',
            '"control".equals(MODE)','"plain".equals(MODE)',
            '"empty".equals(MODE)','"timed".equals(MODE)',
            '"erb".equals(NAMESPACE)',
            "original.tryCast(value)","original.getBaseClass()",
            "original.test(entity)","if (!wrapEnabled()) return original;",
            "if(!wrapEnabled())return original;",
            "native_composite_predicate","native_type_try_cast",
            "erb.block","erb.verified","if score @s erb.job",
            "#needs_restore erb.tmp 1",
        ):
            self.assertIn(needle,java)
        self.assertIn("CompilerSelector022Probe.buildStart(commandInput)",parent)
        self.assertIn("CompilerSelector022Probe.buildEnd(commandInput)",parent)
        self.assertIn('"CompilerSelector022Mixin"',mixins)
        self.assertEqual(commands.count('Commands.literal("cpu022-start")'),2)
        self.assertEqual(commands.count('Commands.literal("cpu022-stop")'),2)
        for term in ("@ModifyArg","EntityTypeTest","Predicate",
                     "getEntities(","sortAndLimit(","getPredicate(","addEntities("):
            self.assertIn(term,mx)
        for absent in ("ci.cancel()","ci.setReturnValue(",
                       "queueNext(","incrementCost()"):
            self.assertNotIn(absent,java+mx)
        for term in ('EXACT_ORIGINAL_LINE','data/erb/function/restore/job_tick.mcfunction',
                     'cpu_family="022"','time.sleep(WINDOW_SECONDS)',
                     '"new_compiled_opcode":False','"full_restoration_claim":False'):
            self.assertIn(term,runner)
        self.assertEqual(ir.MODES,("control","plain","empty","timed"))

    def test_native_empty_timed_clock_signed_and_no_speedup(self):
        data={mode:arm(mode) for mode in ir.MODES}
        result=ir.analysis(data)
        self.assertFalse(result["causal_speedup_claim"])
        self.assertFalse(result["world_restoration_claim"])
        self.assertTrue(result["diagnostic_proxy_objects_are_perturbing_observers"])
        self.assertTrue(result["type_rejected_total_not_directly_observed"])
        self.assertTrue(result["tag_only_rejected_total_not_directly_observed"])
        for row in result["rows"].values():
            self.assertEqual(row["signed_corrected_ns_per_call"],300)
            self.assertFalse(row["removable_cpu_claim"])
        bad=copy.deepcopy(data)
        bad["timed"]["cpu_rows"]["native_composite_predicate"]["passed"]-=2
        with self.assertRaises(AssertionError):
            ir.analysis(bad)
        bad=copy.deepcopy(data)
        bad["timed"]["cpu_rows"]["selector_sort_and_limit"]["passed"]-=10
        with self.assertRaises(AssertionError):
            ir.analysis(bad)
        bad=copy.deepcopy(data)
        bad["control"]["cpu_rows"]["selector_find_entire"]["visits"]=10
        with self.assertRaises(AssertionError):
            ir.analysis(bad)

    def test_log_parser_strict_mode_and_control_unwrapped(self):
        def log(mode):
            data=arm(mode)["cpu_rows"]
            parts=["FC_CPU022_BEGIN mode="+mode]
            for name,info in data.items():
                parts.append("FC_CPU022_ROW kind="+name+" "+
                    " ".join(f"{key}={value}" for key,value in info.items()))
            parts.append("FC_CPU022_END mode="+mode)
            return "\n".join(parts)
        for mode in ir.MODES:
            parsed=ir.parse_cpu022(log(mode),mode)
            self.assertEqual(set(parsed),set(ir.STREAMS))
        with self.assertRaises(AssertionError):
            ir.parse_cpu022(log("control").replace("native_type_try_cast stride=256 visits=0",
                                                     "native_type_try_cast stride=256 visits=1"),
                          "control")
        with self.assertRaises(AssertionError):
            ir.parse_cpu022(log("timed").replace("invalid=0","invalid=1",1),"timed")
        with self.assertRaises(AssertionError):
            ir.parse_cpu022(log("timed").replace("FC_CPU022_END mode=timed",""),"timed")
        with self.assertRaises(AssertionError):
            ir.parse_cpu022(log("plain").replace("cpu_ns=0","cpu_ns=400",1),"plain")

    def test_original_fixture_and_observer_are_distinct_from_optimization(self):
        runner=(ROOT/"scripts/ci_typed_ir022_cpu.py").read_text()
        setup=(ROOT/"scripts/ci_typed_ir019_blastback.py").read_text()
        for term in ('env["FC_CPU022_MODE"] = cpu_mode',
                     'env["FC_CPU022_NAMESPACE"] = "erb"',
                     '"FC_COMPILER_EXEC_CENSUS"] = "false"'):
            self.assertIn(term,setup)
        for term in ('"control"','"plain"','"empty"','"timed"',
                     '"no_compiler":True','"causal_speedup_claim":False',
                     'fc_blastback_probe','pre_event_actor_probes','pre_event_clone_attempts',
                     'read_thread_schedstat(','event_cpu_delta('):
            self.assertIn(term,runner)

if __name__=="__main__":
    unittest.main()
