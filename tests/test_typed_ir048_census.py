"""IR048 lexical admission and fail-closed census parser contracts."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir048_census import shape, parse_log

class Census(unittest.TestCase):
    def test_observed_shape_families(self):
        self.assertEqual(shape('execute as @e[tag="as at",type=minecraft:marker] at @s run function x:y'), "as_at")
        self.assertEqual(shape("execute if score #g obj matches 4 as @e[tag=t] at @s run function x:y"), "score_as_at")
        self.assertEqual(shape("execute as @e[tag=t] if score @s obj = #active obj run function x:y"), "as_score")

    def test_decline_other_shapes(self):
        for s in ("execute as @a at @s run function #x:y",
                  "execute as @a at @s run function x:y with storage x:z",
                  "execute as @a at @s run return run function x:y",
                  "execute as @a at @e run function x:y",
                  "execute as @a positioned ~ ~ ~ run function x:y",
                  "execute as @e[tag=$(tag)] at @s run function x:y",
                  "execute as @a at @s if score @s obj matches 1 run function x:y"):
            self.assertIsNone(shape(s), s)

    def test_parse_native_counts(self):
        raw = ("IR048_CENSUS_BEGIN\nIR048_SITE id=0 builds=3 terminals=6\n"
               "IR048_STAGE id=0 key=execute/as/targets calls=3 returns=3 outputs=6 max_outputs=3 forked_calls=3\n"
               "IR048_CENSUS_END invalid=0\n")
        self.assertEqual(parse_log(raw, [{"id": 0}])[0]["fresh_native"]["terminal_invocations"], 6)
        for bad in (raw.replace("invalid=0", "invalid=1"), raw.replace("outputs=6", "outputs=10"), raw.replace("id=0 builds", "id=1 builds")):
            with self.assertRaises(AssertionError):
                parse_log(bad, [{"id": 0}])

if __name__ == "__main__":
    unittest.main()
