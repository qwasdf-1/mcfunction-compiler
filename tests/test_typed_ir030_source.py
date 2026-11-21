"""IR-030 static original-source sequence test; no Minecraft runtime."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir030_source import COMMANDS, noncomment_commands, validate_sequence


class IR030SourceTests(unittest.TestCase):
    def test_original_order(self):
        rows = validate_sequence("\n".join(COMMANDS) + "\n")
        self.assertEqual([r["source_index_zero_based"] for r in rows],
                         [0, 1, 2, 3, 4])

    def test_comments_are_ignored(self):
        text = "# comment\n" + "\n\n#ignore\n".join(COMMANDS)
        self.assertEqual(noncomment_commands(text), COMMANDS)

    def test_swapped_axes_declined(self):
        corrupted = list(COMMANDS)
        corrupted[2], corrupted[4] = corrupted[4], corrupted[2]
        with self.assertRaisesRegex(AssertionError, "five ordered commands"):
            validate_sequence("\n".join(corrupted))

    def test_extra_command_declined(self):
        with self.assertRaises(AssertionError):
            validate_sequence("\n".join((*COMMANDS, "say unexpected")))

    def test_missing_command_declined(self):
        with self.assertRaises(AssertionError):
            validate_sequence("\n".join(COMMANDS[:-1]))


if __name__ == "__main__":
    unittest.main()
