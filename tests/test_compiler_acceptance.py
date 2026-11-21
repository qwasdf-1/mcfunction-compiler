"""Acceptance-census parser contracts; synthetic tests, not Minecraft execution."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_compiler_acceptance import parse_acceptance_log


class AcceptanceLogTests(unittest.TestCase):
    def parse(self, data: str) -> dict:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "acceptance.log"
            path.write_text(data, encoding="utf-8")
            return parse_acceptance_log(path)

    def test_multiple_outcomes_conserve_events_and_namespaces(self):
        report = self.parse(
            "[main] FC_ACCEPTANCE_BEGIN namespace=vm events=5 keys=3\n"
            "[main] FC_ACCEPTANCE_ROW function=vm:queue/drain outcome=chain_fully_lowered count=2 input=execute if score @s test matches 1 run scoreboard players add #x x 1\n"
            "[main] FC_ACCEPTANCE_ROW function=vm:queue/drain outcome=chain_terminal_only count=1 input=execute if score @s test matches 1 run scoreboard players get #x x\n"
            "[main] FC_ACCEPTANCE_ROW function=vm:macro outcome=macro_parameter_cache_hit count=2 input=\n"
            "[main] FC_ACCEPTANCE_END namespace=vm events=5\n"
        )
        self.assertEqual(report["events"], 5)
        self.assertEqual(report["outcomes"]["chain_fully_lowered"], 2)
        self.assertEqual(report["outcomes"]["chain_terminal_only"], 1)
        self.assertEqual(report["unique_rows"], 3)

    def test_missing_dump_is_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("[main] FC_ACCEPTANCE_ROW function=vm:x outcome=bare_declined count=1 input=x\n")

    def test_mismatched_count_is_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(
                "FC_ACCEPTANCE_BEGIN namespace=vm events=4 keys=1\n"
                "FC_ACCEPTANCE_ROW function=vm:x outcome=bare_declined count=1 input=x\n"
                "FC_ACCEPTANCE_END namespace=vm events=4\n"
            )

    def test_namespace_spill_is_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(
                "FC_ACCEPTANCE_BEGIN namespace=vm events=1 keys=1\n"
                "FC_ACCEPTANCE_ROW function=other:x outcome=bare_declined count=1 input=x\n"
                "FC_ACCEPTANCE_END namespace=vm events=1\n"
            )


if __name__ == "__main__":
    unittest.main()
