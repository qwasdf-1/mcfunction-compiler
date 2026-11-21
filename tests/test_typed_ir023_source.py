"""IR-023 original-source audit contracts: conservative, pinned and explicitly non-native."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ci_typed_ir023_source import EXACT_SELECTOR, audit_archive


def example_archive(commands: list[str] | None = None) -> bytes:
    lines = ["say first", "say second", "say third", "say fourth", EXACT_SELECTOR]
    lines.extend(commands or [])
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("data/erb/function/restore/job_tick.mcfunction",
                         "\n".join(lines) + "\n")
        archive.writestr("data/erb/function/lifecycle.mcfunction",
                         "tag @e[type=minecraft:marker] add erb.block\n")
    return data.getvalue()


class IR023SourceContracts(unittest.TestCase):
    def test_pinned_exact_target_and_mutation_uncertainty(self):
        content = example_archive([
            "execute if score #x obj matches 1 run tag @s remove erb.verified",
            "summon minecraft:marker ~ ~ ~ {Tags:[\"erb.block\"]}",
            "kill @e[type=minecraft:marker,tag=erb.block]",
            "data merge entity @s {Tags:[\"erb.verified\"]}",
            "$execute if score #x obj matches $(n) run tag @s add erb.verified",
        ])
        report = audit_archive(content, hashlib.sha256(content).hexdigest())
        counts = report["totals"]
        self.assertEqual(counts["exact_selector"], 1)
        self.assertEqual(counts["watched_tag_add"], 1)
        self.assertEqual(counts["watched_tag_remove"], 1)
        self.assertEqual(counts["summon_source_site"], 1)
        self.assertEqual(counts["kill_source_site"], 1)
        self.assertEqual(counts["entity_nbt_edit_unresolved"], 1)
        self.assertEqual(counts["nbt_tags_reference_unresolved"], 2)
        self.assertEqual(counts["macro_unresolved"], 1)
        self.assertFalse(report["selector_optimization_implemented"])
        self.assertFalse(report["causal_speedup_claim"])
        self.assertTrue(report["requires_native_mutation_and_visibility_study"])

    def test_hash_pin_fails_closed(self):
        content = example_archive()
        with self.assertRaisesRegex(AssertionError, "SHA mismatch"):
            audit_archive(content, "0" * 64)

    def test_changed_exact_selector_fails_closed(self):
        content = example_archive()
        wrong = content.replace(b"tag=!erb.verified", b"tag=erb.verified")
        with self.assertRaisesRegex(AssertionError, "index-4 selector changed"):
            audit_archive(wrong, hashlib.sha256(wrong).hexdigest())

    def test_source_not_mutation_count(self):
        content = example_archive(["function erb:restore/job_tick",
                                   "tag @s add erb.something_else",
                                   "execute as @e[tag=erb.block] run say hello"])
        result = audit_archive(content, hashlib.sha256(content).hexdigest())
        self.assertEqual(result["totals"].get("watched_tag_add"), 1)
        self.assertEqual(result["totals"].get("watched_tag_remove", 0), 0)
        self.assertEqual(result["totals"]["related_selector_or_tag_read"], 1)


if __name__ == "__main__":
    unittest.main()
