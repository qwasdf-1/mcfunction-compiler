"""IR-031 bytecode report parser/contract tests; no Minecraft runtime claims."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir030_inspect import method_sections
from ci_typed_ir031_inspect import focused_methods


class IR031InspectionTests(unittest.TestCase):
    def test_entity_load_and_component_set_are_separate_methods(self):
        javap = (
            "Compiled from \"Entity.java\"\n"
            "  public void load(ValueInput);\n"
            "    descriptor: (LValueInput;)V\n"
            "    Code:\n"
            "       0: aload_0\n"
            "       1: invokevirtual #4 // Method readAdditionalSaveData:(LValueInput;)V\n"
            "  public <T> void setComponent(DataComponentType<T>, T);\n"
            "    descriptor: (LDataComponentType;Ljava/lang/Object;)V\n"
            "    Code:\n"
            "       0: aload_0\n"
            "       1: invokevirtual #8 // Method applyImplicitComponent:(LDataComponentType;Ljava/lang/Object;)Z\n"
            "  public void postDataManipulated();\n"
            "    descriptor: ()V\n"
            "    Code:\n"
            "       0: return\n"
        )
        focused = focused_methods(method_sections(javap))
        self.assertEqual(len(focused), 3)
        self.assertTrue(any("load(" in signature for signature in focused))
        self.assertTrue(any("setComponent(" in signature for signature in focused))
        self.assertTrue(any("postDataManipulated(" in signature for signature in focused))

    def test_marker_override_inventory_is_not_inferred_from_entity(self):
        marker = (
            "Compiled from \"Marker.java\"\n"
            "  public final class Marker extends Entity {\n"
            "  public void tick();\n"
            "    descriptor: ()V\n"
            "    Code:\n"
            "       0: return\n"
        )
        methods = method_sections(marker)
        self.assertFalse(any(
            token in section["signature"]
            for section in methods
            for token in ("load(", "postDataManipulated(", "readAdditionalSaveData(")
        ))

    def test_empty_disassembly_does_not_claim_a_fast_path(self):
        self.assertEqual(focused_methods([]), {})


if __name__ == "__main__":
    unittest.main()
