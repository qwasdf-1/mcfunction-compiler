"""IR-019 original publisher Blastback live capture-only research guardrails."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir019_blastback as pilot
from ci_typed_ir015_coverage import PINS


class BlastbackCaptureWindow(unittest.TestCase):
    def test_exact_publisher_and_known_mapped_palette(self):
        self.assertEqual(pilot.PACK,Path(PINS["blastback"]["path"]))
        self.assertEqual(len(pilot.WITNESSES),5)
        self.assertIn("erb:capture/prepare",pilot.ALLOWLIST)
        self.assertIn("erb:capture/check_captured_position",pilot.ALLOWLIST)
        self.assertIn("erb:runtime_tick",pilot.ALLOWLIST)
        self.assertIn("erb:group/add_segment",pilot.CALLEES)

    def test_live_dispatch_is_observed_not_compiled(self):
        s=(ROOT/"scripts/ci_typed_ir019_blastback.py").read_text()
        for text in (
            '"dispatch_lowering":False',
            '"cpu_speedup_claim":False',
            '"full_restoration_claim":False',
            '"native_gameplay_parity_claim":False',
            '"FC_SCORE_ADD_PROTOTYPE":"false"',
            '"FC_TYPED_IR_MODE":""',
            '"FC_COMPILER_EXEC_CENSUS":"true"',
            'time.sleep(30)',
            "report[\"capture_stage_observed\"]=bool(reached)",
            "report[\"valid_capture_window\"]=tick_after>tick_before and bool(reached)",
            '"full_restoration_validated"]=False',
        ):
            self.assertIn(text,s)
        self.assertNotIn('report["restoration_gate_passed"]=True',s)
        self.assertNotIn('speedup_percent',s)


if __name__=="__main__":
    unittest.main()
