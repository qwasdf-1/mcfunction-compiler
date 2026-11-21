"""Static tests for IR-030 method-inspection report (not Minecraft runtime)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir030_inspect import lock_properties, method_sections, focused_sites


class IR030InspectionTests(unittest.TestCase):
    def test_lock_parses_comments_and_equals(self):
        props = lock_properties(
            "# heading\nminecraft.version=26.3\n"
            "verification.current_26.3_classfile_artifact_sha256=abc==\n")
        self.assertEqual(props["minecraft.version"], "26.3")
        self.assertEqual(props["verification.current_26.3_classfile_artifact_sha256"], "abc==")
        self.assertNotIn("# heading", props)

    def test_focused_call_attributed_to_correct_method(self):
        disassembly = (
            "Compiled from \"DataCommands.java\"\n"
            "  public static int first();\n"
            "    descriptor: ()I\n"
            "    Code:\n"
            "       0: aload_0\n"
            "       1: invokevirtual #10 // Method DataAccessor.getData:()Lnet/minecraft/nbt/CompoundTag;\n"
            "  private static int second();\n"
            "    descriptor: ()I\n"
            "    Code:\n"
            "       0: invokestatic #21 // Method DataCommands.getSingleTag:()V\n"
        )
        methods = method_sections(disassembly)
        self.assertEqual(len(methods), 2)
        sites = focused_sites(methods)
        self.assertTrue(any("first()" in r["method"] and "getData" in r["instruction"]
                            for r in sites))
        self.assertTrue(any("second()" in r["method"] and "getSingleTag"
                            in r["instruction"] for r in sites))
        self.assertFalse(any("second()" in r["method"] and "getData"
                             in r["instruction"] for r in sites))

    def test_empty_bytecode_not_claimed(self):
        self.assertEqual(method_sections("public class Fake {}\n"), [])
        self.assertEqual(focused_sites([]), [])


if __name__ == "__main__":
    unittest.main()
