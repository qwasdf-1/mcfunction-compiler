"""IR029 JFR attribution contracts and JSON parser tests."""
from pathlib import Path
import sys,tempfile,json,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir029_jfr as p
class IR029JFR(unittest.TestCase):
    def test_abba_has_only_compiled_fork_switch(self):
        self.assertEqual(p.RUN_ORDER,(
            ("A1","plan_only"),("B1","compiled"),
            ("B2","compiled"),("A2","plan_only")))
        a=p.cpu.mode_options("plan_only")
        b=p.cpu.mode_options("compiled")
        self.assertEqual(set(a),set(b))
        self.assertEqual({k:v for k,v in a.items() if k!="FC_TYPED_IR_COMPILED_FORK"},
                         {k:v for k,v in b.items() if k!="FC_TYPED_IR_COMPILED_FORK"})
        self.assertEqual(a["FC_TYPED_IR_COMPILED_FORK"],"false")
        self.assertEqual(b["FC_TYPED_IR_COMPILED_FORK"],"true")
        self.assertEqual(a["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(a["FC_TYPED_IR_REENTRANT_SAFE"],"true")

    def test_jfr_profile_is_separate_from_cpu_clock_measurement(self):
        src=(ROOT/"scripts/ci_typed_ir029_jfr.py").read_text()
        for token in ("JFR.start","settings=profile","JFR.dump",
                      "jdk.ExecutionSample","server_thread_os_tid",
                      "BuildContexts","brigadier_run_modifier",
                      "entity_selector_find","source_with_entity",
                      "compiled_executor_run","scoreboard_player_lookup",
                      "continuation_schedule","categories_are_overlapping",
                      "jfr_profile_is_not_cpu_benchmark"):
            self.assertIn(token,src)
        self.assertNotIn("read_thread_schedstat(",src)
        self.assertNotIn("event_cpu_delta(",src)

    def test_parse_jfr_json_filters_exact_server_os_thread(self):
        event={"type":"jdk.ExecutionSample","values":{
            "sampledThread":{"osThreadId":42,"javaName":"Server thread"},
            "state":"STATE_RUNNABLE",
            "stackTrace":{"frames":[
                {"method":{"type":{"name":"dev.functioncompiler.CompilerForkExecutor025"},
                           "name":"run"}},
                {"method":{"type":{"name":"net.minecraft.commands.arguments.selector.EntitySelector"},
                           "name":"findEntities"}},
            ]}}}
        payload={"recording":{"events":[event]*p.MIN_SAMPLES}}
        with tempfile.NamedTemporaryFile(suffix=".jfr") as f:
            from unittest.mock import patch
            with patch.object(p.subprocess,"run",
                              return_value=type("R",(),{
                                  "returncode":0,"stdout":json.dumps(payload),"stderr":""})()):
                summary=p.summarize_jfr(Path(f.name),42)
        self.assertEqual(summary["server_thread_runnable_samples"],p.MIN_SAMPLES)
        self.assertEqual(summary["inclusive_stack_sample_counts"]["compiled_executor_run"],
                         p.MIN_SAMPLES)
        self.assertEqual(summary["inclusive_stack_sample_counts"]["entity_selector_find"],
                         p.MIN_SAMPLES)
        self.assertTrue(summary["categories_are_overlapping"])

if __name__=="__main__":unittest.main()
