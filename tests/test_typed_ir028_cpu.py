"""IR028 uninstrumented ABBA original publisher CPU research safeguards."""
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir028_cpu as s
class IR028Cpu(unittest.TestCase):
    def test_preregistered_AA_AB_modes_and_exact_single_switch(self):
        self.assertEqual(s.RUN_ORDER,(
            ("A1","plan_only"),("B1","compiled"),("B2","compiled"),("A2","plan_only")))
        self.assertEqual(s.TARGET_TICKS,600)
        self.assertEqual(s.MAX_AA_RELATIVE_SPREAD,.08)
        for mode in ("plan_only","compiled"):
            actual=s.mode_options(mode)
            original=s.BASE_OPTIONS(mode)
            self.assertEqual(actual["FC_TYPED_IR_MODE"],"bytecode")
            self.assertEqual(actual["FC_TYPED_IR_FUNCTION_FILTER"],
                             "erb:restore/job_tick")
            self.assertEqual(actual["FC_TYPED_IR_NATIVE_FORK_PLAN"],"true")
            self.assertEqual(actual["FC_TYPED_IR_COMPILED_FORK"],
                             str(mode=="compiled").lower())
            self.assertEqual(actual["FC_TYPED_IR_DIAGNOSTICS"],"false")
            self.assertEqual(actual["FC_COMPILER_EXEC_CENSUS"],"false")
            self.assertEqual(actual["FC_TYPED_IR_REENTRANT_SAFE"],"true")
            self.assertEqual(actual["FC_TYPED_IR_SCORE_CACHE"],"false")
            self.assertEqual(actual["FC_TYPED_IR_DIRECT_FUNCTION"],"false")
            self.assertEqual(original["FC_TYPED_IR_NATIVE_FORK_PLAN"],"true")

    def test_original_event_CPU_starts_before_TNT_not_after_spawn(self):
        source=(ROOT/"scripts/ci_typed_ir028_cpu.py").read_text()
        a=source.index("cpu_before=read_thread_schedstat(")
        b=source.index("base.verify_started_actor(client)")
        c=source.index("cpu_after=read_thread_schedstat(")
        self.assertTrue(a<b<c)
        for token in (
            "find_server_thread(proc.pid)",
            "cgroup_throttle_count()",
            "event_cpu_delta(",
            "original_datapack_unchanged",
            "oracle.configure_stable_original_scene(client)",
            "actual_original_capture_markers_seen",
            "oracle.observe(client",
            "whole_template_equal",
            "native_tnt_remaining",
            "all_host_valid",
            "A_A_relative_spread",
            "B_relative_cpu_change_observed",
            "causal_speedup_confirmed",
            "performance_promotion_eligible",
        ):
            self.assertIn(token,source)
        self.assertNotIn("FC_TYPED_IR_DIAGNOSTICS\":\"true",source)
        self.assertNotIn("functioncompiler ir025",source)

if __name__=="__main__":unittest.main()
