"""Entry/callback census parser contracts. No server execution is simulated."""
from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_compiler_execution import parse_exec_census, top_sites


class EventCensusTests(unittest.TestCase):
    def parse(self, text: str) -> dict:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "exec-census.log"
            p.write_text(text, encoding="utf-8")
            return parse_exec_census(p)

    def good(self) -> str:
        return (
            "FC_EXEC_BEGIN namespace=vm sites=3 entries=32 callbacks=40 overflow=0 targets=4\n"
            "FC_EXEC_ROW function=vm:queue/drain index=0 entries=30 callbacks=40 kind=ordinary_callback input=execute as @e run scoreboard players add #x obj 1\n"
            "FC_EXEC_ROW function=vm:operation/claim index=2 entries=2 callbacks=0 kind=custom_executor input=return run function vm:stop\n"
            "FC_EXEC_ROW function=vm:detection/upsert_target index=1 entries=0 callbacks=0 kind=ordinary_callback input=tp @s ~ ~ ~\n"
            "FC_EXEC_END namespace=vm sites=3 entries=32 callbacks=40 overflow=0\n"
        )

    def test_counts_and_fork_cardinality(self):
        out = self.parse(self.good())
        self.assertEqual(out["entries"], 32)
        self.assertEqual(out["ordinary_callbacks"], 40)
        self.assertEqual(top_sites(out)[0]["function"], "vm:queue/drain")
        self.assertEqual(out["rows"][2]["entries"], 0)

    def test_overflow_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "Lost 1"):
            self.parse(self.good().replace("overflow=0", "overflow=1"))

    def test_incomplete_dump_rejected(self):
        with self.assertRaisesRegex(ValueError, "Exactly one"):
            self.parse(self.good().split("FC_EXEC_END")[0])

    def test_nonconservation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "conserve"):
            self.parse(self.good().replace("entries=30 callbacks=40", "entries=29 callbacks=40"))

    def test_nonordinary_callback_is_not_misclassified(self):
        with self.assertRaisesRegex(ValueError, "non-Brigadier"):
            self.parse(self.good().replace(
                "index=2 entries=2 callbacks=0 kind=custom_executor",
                "index=2 entries=2 callbacks=1 kind=custom_executor"))

    def test_duplicate_site_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.parse(self.good().replace(
                "function=vm:detection/upsert_target index=1",
                "function=vm:queue/drain index=0"))

    def test_out_of_namespace_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "out-of-scope"):
            self.parse(self.good().replace(
                "function=vm:detection/upsert_target",
                "function=another:detection/upsert_target"))


if __name__ == "__main__":
    unittest.main()
