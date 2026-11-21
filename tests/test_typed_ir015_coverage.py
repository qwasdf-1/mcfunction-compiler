"""IR-015 source coverage contracts, not evidence of runtime compiler activation."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir015_coverage as audit


class IR015CoverageContract(unittest.TestCase):
    def test_exact_supported_source_shapes(self):
        accepted = (
            ("scoreboard players set #a o -12", "mutation"),
            ("scoreboard players add #a o 1", "mutation"),
            ("scoreboard players remove #a o 3", "mutation"),
            ("scoreboard players operation #a o += #b o", "binary"),
            ("scoreboard players operation #a o *= #a o", "binary"),
            ("execute if score #guard o matches 7 run "
             "scoreboard players add #a o 1", "guard"),
            ("execute unless score #guard o matches -4 run "
             "scoreboard players set #a o 0", "guard"),
        )
        for line, expected in accepted:
            self.assertEqual(audit.shape(line), expected)

    def test_unsupported_and_macro_source_are_barriers(self):
        declined = (
            "scoreboard players add @s o 1",
            "scoreboard players operation #a o /= #b o",
            "scoreboard players get #a o",
            "execute if block ~ ~ ~ stone run scoreboard players set #a o 1",
            "execute if score #a o matches 1..5 run scoreboard players set #a o 1",
            "execute as @s run scoreboard players add #a o 1",
            "function pack:child",
            "return 0",
            "scoreboard players add #a o $(value)",
            "execute if score #guard o matches 7 run function pack:child",
            "execute store result storage vm:queue head int 1 run scoreboard players get #a o",
        )
        for line in declined:
            self.assertIsNone(audit.shape(line), line)

    def test_segmentation_and_whole_function_gate(self):
        a="scoreboard players add #a o 1"
        b="function p:child"
        def summary(lines):
            s=audit.segment(lines)
            return (s["source_shaped_region_commands"],
                    len(s["candidate_regions"]),
                    s["source_shaped_singletons"],
                    s["possible_direct_function"])
        self.assertEqual(summary([a]), (0,0,1,False))
        self.assertEqual(summary([a,a]), (2,1,0,True))
        self.assertEqual(summary([a]*64), (64,1,0,True))
        self.assertEqual(summary([a]*65), (64,1,1,False))
        self.assertEqual(summary([a]*66), (66,2,0,True))
        self.assertEqual(summary([a]*4096), (4096,64,0,True))
        self.assertEqual(summary([a]*4097), (4096,64,1,False))
        self.assertEqual(summary([a,b,a,a]), (2,1,1,False))
        self.assertEqual(summary([b,a,a,b,a,a]), (4,2,0,False))

    def test_pinned_sources_and_explicit_read_only_semantics(self):
        self.assertEqual(audit.PINS["veinminer"]["sha256"],
                         "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e")
        self.assertEqual(audit.PINS["blastback"]["sha256"],
                         "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90")
        source=Path(audit.__file__).read_text()
        self.assertIn("source_shape_only_not_parsed_or_executed", source)
        self.assertIn("candidate_regions",source)
        self.assertIn("tick_scope", source)
        self.assertNotIn("performance_gain",source)


if __name__ == "__main__":
    unittest.main()
