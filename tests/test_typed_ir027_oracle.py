"""IR027 original native complete-vs-active restoration oracle source contracts."""
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir027_native_oracle as o

class IR027OriginalOracle(unittest.TestCase):
    def test_original_publisher_and_two_native_no_compiler_arms(self):
        self.assertEqual(o.base.TARGET,"erb:restore/job_tick")
        self.assertEqual(o.base.PIN,
            "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90")
        self.assertEqual(o.TICK_TARGETS,(600,1200,2400))
        self.assertEqual(o.NO_EVENT_TICKS,600)
        self.assertEqual(o.MAX_WAIT_SECONDS,210)
        self.assertEqual(o.base.options("native")["FC_TYPED_IR_MODE"],"")
        self.assertEqual(len(o.base.WITNESSES),5)
        oracle=(ROOT/"scripts/ci_typed_ir027_native_oracle.py").read_text()
        self.assertIn("configure_stable_original_scene(client)",oracle)
        self.assertIn("fill -4 56 -4 12 72 12 minecraft:stone",oracle)
        self.assertIn("controlled_full_stone_17_cube",oracle)
        self.assertIn("natural_IR026_terrain_comparability_claim",oracle)

    def test_finish_condition_uses_original_job_marker_cleanup_not_scratch_flag(self):
        s=(ROOT/"scripts/ci_typed_ir027_native_oracle.py").read_text()
        for token in (
            'base.launch("native")','base.original_publisher()',
            "base.verify_started_actor(client)",
            '"no_tnt","native_tnt"',
            'client.command("function erb:status/collect")',
            'base.native_witnesses(client)',
            '"restore_job"','"job_marker"','"unresolved"','"verifying"',
            '"retry_3plus"','"verify_wait"','"fluid_eligible"',
            '"late_eligible"','"whole_template_equal"',
            'result["original_job_complete"]=(saved==0 and jobs==0)',
            'result["original_template_restored"]=last["whole_template_equal"]',
            'result["status"]="native_restore_not_complete"',
            '"native_completion_oracle_blocked"',
            '"cpu_promotion_gate_open"]=False',
            '"snapshot" if False else "checkpoints"',
        ):
            if 'if False' in token:continue
            self.assertIn(token,s)
        self.assertNotIn('FC_TYPED_IR_COMPILED_FORK":"true"',s)
        for required in ("prove_original_capture_activity(", "original_capture_witness",
                         "max_original_block_markers", "first_original_capture",
                         "tnt_remaining_after", "The originally spawned TNT actor never detonated"):
            self.assertIn(required,s)
        self.assertNotIn("System.nanoTime(",s)

    def test_markers_and_mismatch_layers_are_read_only(self):
        s=(ROOT/"scripts/ci_typed_ir027_native_oracle.py").read_text()
        for token in (
            "execute store result score {holder} fc_probe",
            "if entity {selector}","execute if blocks -4 {y} -4",
            'range(56,73)','marker_counts',
            'markers["block"]!=markers["verified"]+markers["eligible"]',
            "observation_tick_span","native_world",
        ):
            if token=="native_world":continue
            self.assertIn(token,s)
        self.assertNotIn("execute as {selector} run scoreboard players add",s)
if __name__=="__main__":unittest.main()
