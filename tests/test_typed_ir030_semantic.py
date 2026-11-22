"""Pure report/guard tests for the IR-030 live Minecraft semantic runner."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir030_semantic import compare, must_not_fail, stat_value, xyz


def arm(label, candidate=False):
    return {
        "label": label,
        "free_marker": {"function_response": "Executed free", "frontier": (-2, 64, -1)},
        "passenger_entity": {"function_response": "Executed passenger", "ride_success": 1, "frontier": (10, 65, 20)},
        "nonmarker": {"function_response": "Executed nonmarker", "frontier": (-2, 64, -1)},
        "missing_path": {"function_response": "Executed missing", "frontier": (0, 0, 0)},
        "invalid_target_response": "No entity was found",
        "ir030_counters": {
            "ir030_pos_compiled_x": 1 if candidate else 0,
            "ir030_pos_compiled_y": 1 if candidate else 0,
            "ir030_pos_compiled_z": 1 if candidate else 0,
            "ir030_pos_fast_x": 1 if candidate else 0,
            "ir030_pos_fast_y": 1 if candidate else 0,
            "ir030_pos_fast_z": 1 if candidate else 0,
            "ir030_pos_verified": 3 if candidate else 0,
            "ir030_pos_verify_mismatches": 0,
            "ir030_pos_invalid_targets": 0,
            "ir030_pos_fallback_vehicle": 1 if candidate else 0,
            "ir030_pos_fallback_entity_type": 3 if candidate else 0,
            "ir030_pos_fallback_nonfinite": 0,
        },
    }


class IR030SemanticTests(unittest.TestCase):
    def test_negative_coordinate_parser(self):
        self.assertEqual(xyz("Marker has the following entity data: [{x:-2,y:64,z:-1}]"),
                         (-2, 64, -1))

    def test_xyz_requires_three_axes(self):
        with self.assertRaisesRegex(AssertionError, "Could not parse"):
            xyz("Marker has the following entity data: {x:-2,y:64}")

    def test_candidate_parity_report_accepts_expected_fallbacks(self):
        result = compare(arm("control"), arm("candidate", True))
        self.assertEqual(result["status"], "accepted_candidate_fixture_parity")
        self.assertTrue(result["passenger_native_fallback_verified"])

    def test_frontier_mismatch_rejected(self):
        candidate = arm("candidate", True)
        candidate["passenger_entity"]["frontier"] = (11, 65, 20)
        with self.assertRaisesRegex(AssertionError, "frontier mismatch"):
            compare(arm("control"), candidate)

    def test_native_verification_mismatch_rejected(self):
        candidate = arm("candidate", True)
        candidate["ir030_counters"]["ir030_pos_verify_mismatches"] = 1
        with self.assertRaisesRegex(AssertionError, "NBT or feedback mismatch"):
            compare(arm("control"), candidate)

    def test_missing_fast_axis_rejected(self):
        candidate = arm("candidate", True)
        candidate["ir030_counters"]["ir030_pos_fast_y"] = 0
        with self.assertRaisesRegex(AssertionError, "did not take all three"):
            compare(arm("control"), candidate)

    def test_unmounted_passenger_fixture_rejected(self):
        candidate = arm("candidate", True)
        candidate["passenger_entity"]["ride_success"] = 0
        with self.assertRaisesRegex(AssertionError, "did not mount"):
            compare(arm("control"), candidate)

    def test_status_counter_must_be_present(self):
        with self.assertRaisesRegex(AssertionError, "Missing"):
            stat_value("wrapped=true", "ir030_pos_fast_x")

    def test_expected_errors_are_not_silently_accepted(self):
        with self.assertRaisesRegex(RuntimeError, "failed"):
            must_not_fail("fixture", "Failed to execute command")


if __name__ == "__main__":
    unittest.main()
