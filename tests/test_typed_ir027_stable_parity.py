"""IR027 controlled original Blastback native, plan-only, compiled full-restoration."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir027_stable_parity as s
class IR027CompleteSemanticContracts(unittest.TestCase):
    def test_original_publisher_complete_world_contract(self):
        self.assertEqual(s.MODES,("native","plan_only","compiled"))
        self.assertEqual(s.CHECKPOINTS,(600,900))
        self.assertIn("block",s.REQUIRED_GONE)
        self.assertIn("restore_job",s.REQUIRED_GONE)
        self.assertIn("job_marker",s.REQUIRED_GONE)
        self.assertIn("saved",s.STATUS_EQUAL)
        self.assertIn("groups",s.STATUS_EQUAL)
        self.assertEqual(s.base.TARGET,"erb:restore/job_tick")

    def test_real_original_event_and_full_volume_not_just_named_blocks(self):
        src=(ROOT/"scripts/ci_typed_ir027_stable_parity.py").read_text()
        for token in (
            "base.launch(mode)","base.original_publisher()",
            "oracle.configure_stable_original_scene(client)",
            "base.ledger_gate(client,mode)",
            "base.verify_started_actor(client)",
            "oracle.prove_original_capture_activity(",
            "original_capture_witness","checkpoint_accepted",
            "whole_template_equal","y_slice_equal",
            "all_original_job_and_block_markers_gone",
            'if report["native_tnt_remaining"]!=0',
            "selected_sources","compiled_forks","executed_forks",
            "native_fallbacks","normalized_equal",
            "same_work_restoration_gate","performance_claim",
        ):
            self.assertIn(token,src)
        self.assertNotIn("from ci_typed_ir025_compiled_fork import",src)

    def test_no_cpu_promotion_while_proving_semantics(self):
        src=(ROOT/"scripts/ci_typed_ir027_stable_parity.py").read_text()
        self.assertIn('"performance_claim":False',src)
        self.assertIn('"cpu_claim":False',src)
        self.assertNotIn("event_cpu_delta(",src)
        self.assertNotIn("FC_TYPED_IR_SCORE_CACHE\":\"true",src)
if __name__=="__main__":unittest.main()
