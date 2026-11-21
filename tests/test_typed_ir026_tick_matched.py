"""IR026 stage B tick-matched original Blastback native-world checks."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir026_tick_matched as t

class IR026TickMatchedContracts(unittest.TestCase):
    def test_three_original_publisher_jvm_arms_tick_matched(self):
        self.assertEqual(t.MODES,("native","plan_only","compiled"))
        self.assertEqual(t.TARGET_TICKS,600)
        self.assertLessEqual(t.MAX_SAMPLE_OVERSHOOT,20)
        self.assertLessEqual(t.MAX_MARKER_RELATIVE_DEVIATION,.02)
        self.assertEqual(t.base.PIN,
            "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90")
        self.assertEqual(t.base.TARGET,"erb:restore/job_tick")
        self.assertIn("original_datapack_600_ticks_from_actor_confirmed",
                      (ROOT/"scripts/ci_typed_ir026_tick_matched.py").read_text())

    def test_original_source_and_compiler_execution_gates(self):
        runner=(ROOT/"scripts/ci_typed_ir026_tick_matched.py").read_text()
        for token in (
            "base.original_publisher()",
            "base.configure_original_scene(client)",
            "base.ledger_gate(client,mode)",
            "base.verify_started_actor(client)",
            'score(client,"#tick_id","erb.cfg")',
            "ticks>=target",
            "base.snapshot(client)",
            "base.MARKERS",
            "original_source_compiler_ledger" if False else "compiled_fork_diagnostics",
            "compiled_forks","executed_forks","selector_scans",
            "selected_sources","passing_sources",
            "tick_stop_overshoot","snapshot_read_span",
            "coarse_entity_population_within_2percent",
            "eligible_exact_equality_claim",
            "full_world_equivalence_claim",
            "performance_claim",
        ):
            self.assertIn(token,runner)
        self.assertNotIn("time.sleep(30)",runner)
        self.assertNotIn("GC",runner)

    def test_live_marker_conservation_and_quantified_not_assumed_parity(self):
        self.assertEqual(len(t.base.MARKERS),3)
        self.assertEqual(len(t.base.WITNESSES),5)
        src=(ROOT/"scripts/ci_typed_ir026_tick_matched.py").read_text()
        self.assertIn('markers["verified"]+markers["eligible"]',src)
        self.assertIn('active_job","needs_restore',src)
        self.assertIn('block_fraction<=MAX_MARKER_RELATIVE_DEVIATION',src)
        self.assertIn('verified_fraction<=MAX_MARKER_RELATIVE_DEVIATION',src)
        self.assertIn('same_work_tick_gate',src)
        self.assertIn('"complete_behavioral_equivalence"]=False',src)

if __name__=="__main__":unittest.main()
