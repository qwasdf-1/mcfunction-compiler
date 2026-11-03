import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_CONFIGURATION = (
    ROOT / "src/main/java/dev/functioncompiler/ProbeConfiguration.java"
)
COMPILER_CONFIG = ROOT / "src/main/java/dev/functioncompiler/CompilerConfig.java"


def method_body(source: str, name: str) -> str:
    match = re.search(
        rf"public static boolean {name}\(\) \{{(.*?)\n    \}}",
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"method {name}() not found")
    return match.group(1)


class ConfigFlagSemanticsTests(unittest.TestCase):
    """Source-contract guard for the disk-config flag plumbing.

    Runtime behavior is covered by the PERF-016 activation diagnostic; this
    test only prevents the standalone flag from becoming dead code again.
    """

    def test_score_add_default_combines_the_disk_flag_and_fusion(self) -> None:
        body = method_body(PROBE_CONFIGURATION.read_text(encoding="utf-8"),
                           "scoreAddPrototypeEnabled")

        self.assertIn("CompilerConfig.isScoreAddEnabled()", body)
        self.assertIn("fusedRegionPrototypeEnabled()", body)

    def test_disk_score_add_flag_still_requires_the_master_switch(self) -> None:
        body = method_body(COMPILER_CONFIG.read_text(encoding="utf-8"),
                           "isScoreAddEnabled")

        self.assertIn("enabled", body)
        self.assertIn("scoreAddEnabled", body)


if __name__ == "__main__":
    unittest.main()
