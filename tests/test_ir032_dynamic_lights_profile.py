"""IR-032 Dynamic Lights runtime census parsing and conservation tests."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "runtime"))

from run_dynamic_lights_profile import parse_exec_census_lines


VALID_LOG = [
    "INFO FC_EXEC_BEGIN namespace=test sites=2 entries=5 callbacks=3 overflow=0 targets=2 callees=2 native_calls=3 single_dispatch_entries=3 complex_dispatch_entries=0",
    "INFO FC_EXEC_ROW function=test:tick index=0 entries=2 callbacks=1 kind=ordinary_callback dispatch_shape=none input=scoreboard players add #x obj 1",
    "INFO FC_EXEC_ROW function=test:tick index=1 entries=3 callbacks=2 kind=ordinary_callback dispatch_shape=single_score_static_call input=execute if score #x obj matches 1 run function test:child",
    "INFO FC_EXEC_CALLEE function=test:child native_call_tasks=2",
    "INFO FC_EXEC_CALLEE function=test:tick native_call_tasks=1",
    "INFO FC_EXEC_END namespace=test sites=2 entries=5 callbacks=3 overflow=0 native_calls=3 single_dispatch_entries=3 complex_dispatch_entries=0",
]


class IR032DynamicLightsProfileTests(unittest.TestCase):
    def test_parses_and_reconciles_exact_census(self):
        report = parse_exec_census_lines(VALID_LOG, "test")
        self.assertEqual(report["summary"]["sites"], 2)
        self.assertEqual(report["summary"]["entries"], 5)
        self.assertEqual(report["summary"]["callbacks"], 3)
        self.assertEqual(report["summary"]["native_calls"], 3)
        self.assertEqual(report["per_function"]["test:tick"], {
            "sites": 2,
            "active_sites": 2,
            "entries": 5,
            "callbacks": 3,
            "active_callback_sites": 2,
        })
        self.assertEqual(report["callee_rows"], [
            {"function": "test:child", "native_call_tasks": 2},
            {"function": "test:tick", "native_call_tasks": 1},
        ])

    def test_rejects_missing_summary_boundary(self):
        with self.assertRaisesRegex(ValueError, "Expected one FC_EXEC_BEGIN"):
            parse_exec_census_lines(VALID_LOG[:-1], "test")

    def test_rejects_wrong_namespace(self):
        with self.assertRaisesRegex(ValueError, "namespace mismatch"):
            parse_exec_census_lines(VALID_LOG, "other")

    def test_rejects_site_row_count_mismatch(self):
        altered = [line for line in VALID_LOG if "FC_EXEC_ROW " not in line]
        with self.assertRaisesRegex(ValueError, "site conservation"):
            parse_exec_census_lines(altered, "test")

    def test_rejects_entry_counter_mismatch(self):
        altered = [
            line.replace("entries=5", "entries=6")
            if "FC_EXEC_END " in line else line
            for line in VALID_LOG
        ]
        with self.assertRaisesRegex(ValueError, "BEGIN/END mismatch"):
            parse_exec_census_lines(altered, "test")

    def test_rejects_registration_overflow(self):
        altered = [
            line.replace("overflow=0", "overflow=1")
            if "FC_EXEC_BEGIN " in line or "FC_EXEC_END " in line else line
            for line in VALID_LOG
        ]
        with self.assertRaisesRegex(ValueError, "registration overflow"):
            parse_exec_census_lines(altered, "test")


if __name__ == "__main__":
    unittest.main()
