"""IR-023 Stage 4 fail-closed source/semantic contracts for native visibility fixtures."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir023_visibility as v


class IR023VisibilityContracts(unittest.TestCase):
    def test_native_selectors_have_explicit_matching_and_order(self):
        self.assertEqual(v.MODES,("native","observer"))
        self.assertEqual(set(v.EXPECTED),
                         {"cycle","raw_cycle","summon_kill","near_limit"})
        self.assertEqual(v.EXPECTED["cycle"],
                         {"#c0":0,"#c1":1,"#c2":1,"#c3":0,"#c4":1,"#c5":0})
        self.assertEqual(v.EXPECTED["raw_cycle"],
                         {"#r0":0,"#r1":1,"#r2":0,"#r3":1,"#r4":0})
        self.assertEqual(v.EXPECTED["summon_kill"],
                         {"#s0":0,"#s1":1,"#s2":0,"#s3":0})
        self.assertEqual(v.EXPECTED["near_limit"],
                         {"#pick0":11,"#pick1":22})
        self.assertEqual(len(v.COMMANDS["cycle"]),12)
        self.assertEqual(len(v.COMMANDS["raw_cycle"]),10)
        self.assertIn("function fc_ir023:nested_child",v.COMMANDS["nested_parent"])
        self.assertTrue(v.COMMANDS["cycle"][0].startswith("summon minecraft:marker"))
        self.assertTrue(v.COMMANDS["raw_cycle"][0].startswith("summon minecraft:marker"))
        self.assertTrue(v.COMMANDS["nested_parent"][0].startswith("summon minecraft:marker"))
        self.assertIn("sort=nearest,limit=1",v.ORDERED_SELECT)
        for name,commands in v.COMMANDS.items():
            with self.subTest(name=name):
                self.assertFalse(any("[INVALID]" in line for line in commands))
                self.assertTrue(all(line and not line.startswith("$") for line in commands))

    def test_native_raw_mutation_bypasses_method_hooks(self):
        java=(ROOT/"src/main/java/dev/functioncompiler/CompilerTagVisibility023Harness.java").read_text()
        commands=(ROOT/"src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        entity_mixin=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerTagMutation023EntityMixin.java").read_text()
        runner=(ROOT/"scripts/ci_typed_ir023_visibility.py").read_text()
        self.assertIn("entity.entityTags().add(tag)",java)
        self.assertIn("entity.entityTags().remove(tag)",java)
        self.assertNotIn("entity.addTag(tag)",java)
        self.assertNotIn("entity.removeTag(tag)",java)
        self.assertIn('entity.entityTags().contains("fc023.fixture")',java)
        self.assertIn("entity instanceof Marker",java)
        self.assertIn('"FC_IR023_VISIBILITY_HARNESS"',commands)
        self.assertEqual(commands.count('Commands.literal("fc_ir023_raw_tag")'),1)
        self.assertIn('"FC_IR023_VISIBILITY_HARNESS":"true"',runner)
        self.assertIn('if case=="raw_cycle" and mode=="observer"',runner)
        self.assertIn("parse_cpu023(raw,\"plain\")",runner)
        self.assertIn("direct_set_invalidation_gap_reproduced",runner)
        self.assertIn("native_semantic_parity",runner)
        self.assertIn('"FC_TYPED_IR_MODE":""',runner)
        self.assertIn('method = "addTag(Ljava/lang/String;)Z"',entity_mixin)
        self.assertIn('method = "removeTag(Ljava/lang/String;)Z"',entity_mixin)
        self.assertNotIn('method = "entityTags()',entity_mixin)
        self.assertNotIn("ci.cancel()",java+entity_mixin)
        self.assertNotIn("ci.setReturnValue(",java+entity_mixin)

    def test_fixture_generation_uses_only_original_commands(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            v.fixture(root)
            data=root/"world/datapacks"/v.PACK/"data/fc_ir023/function"
            self.assertEqual(sorted(p.stem for p in data.glob("*.mcfunction")),
                             sorted(v.COMMANDS))
            for name,commands in v.COMMANDS.items():
                self.assertEqual((data/(name+".mcfunction")).read_text().splitlines(),
                                 commands)
            pack=(root/"world/datapacks"/v.PACK/"pack.mcmeta").read_text()
            self.assertIn('"min_format": [97, 1]',pack)
            self.assertIn('"max_format": [97, 1]',pack)


if __name__=="__main__":
    unittest.main()
