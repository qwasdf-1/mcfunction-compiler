import unittest

from scripts.run_compatibility_probe import (
    MODES,
    mode_bytecode_enabled,
    mode_fused_enabled,
    mode_mod_keys,
    mode_score_add_enabled,
    mode_wrapper_enabled,
)


class CompatibilityProbeConfigurationTests(unittest.TestCase):
    def test_lithium_bellows_moonrise_modes_are_available(self) -> None:
        self.assertTrue(
            {
                "lbm113120-off",
                "lbm113120-on",
                "lbm113120-score-add-on",
                "lbm113120-fused-interpreted",
                "lbm113120-bytecode-emitted",
            }.issubset(MODES)
        )
        self.assertEqual(
            mode_mod_keys("lbm113120-off"),
            ("lithium", "bellows113", "moonrise120"),
        )

    def test_mode_names_select_the_intended_prototypes(self) -> None:
        self.assertFalse(mode_wrapper_enabled("lbm113120-off"))
        self.assertFalse(mode_score_add_enabled("lbm113120-off"))
        self.assertTrue(mode_wrapper_enabled("lbm113120-on"))
        self.assertFalse(mode_score_add_enabled("lbm113120-on"))
        self.assertTrue(mode_score_add_enabled("lbm113120-score-add-on"))
        self.assertFalse(mode_fused_enabled("lbm113120-score-add-on"))
        self.assertTrue(mode_score_add_enabled("lbm113120-fused-interpreted"))
        self.assertTrue(mode_fused_enabled("lbm113120-fused-interpreted"))
        self.assertTrue(mode_bytecode_enabled("lbm113120-bytecode-emitted"))
        self.assertFalse(mode_fused_enabled("lbm113120-bytecode-emitted"))

    def test_existing_fabric_mode_features_remain_classified(self) -> None:
        self.assertFalse(mode_wrapper_enabled("fabric-off"))
        self.assertTrue(mode_wrapper_enabled("fabric-on"))
        self.assertTrue(mode_score_add_enabled("score-add-on"))
        self.assertTrue(mode_fused_enabled("fused-interpreted"))
        self.assertTrue(mode_bytecode_enabled("bytecode-emitted"))


if __name__ == "__main__":
    unittest.main()
