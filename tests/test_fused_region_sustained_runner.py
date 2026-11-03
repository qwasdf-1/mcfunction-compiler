import unittest

from scripts.run_fused_region_sustained import (
    ADD_COMMAND,
    ADDS_PER_TICK,
    generated_files,
    generated_hashes,
)

TICK_SCALED = (
    "data/function_compiler_fused_sustained/function/tick_scaled.mcfunction"
)
TICK_INSTRUMENTED = (
    "data/function_compiler_fused_sustained/function/tick_instrumented.mcfunction"
)


class FusedRegionSustainedRunnerTests(unittest.TestCase):
    def test_default_generation_keeps_the_pristine_tick_function(self) -> None:
        files = generated_files()

        self.assertNotIn(TICK_SCALED, files)
        self.assertIn(
            "function function_compiler_fused_sustained:tick\n",
            files[TICK_INSTRUMENTED],
        )

    def test_scaled_generation_builds_an_exact_contiguous_block(self) -> None:
        files = generated_files(20_000)
        lines = files[TICK_SCALED].splitlines()

        self.assertEqual(len(lines), 20_000)
        self.assertEqual(set(lines), {ADD_COMMAND})
        self.assertIn(
            "function function_compiler_fused_sustained:tick_scaled\n",
            files[TICK_INSTRUMENTED],
        )

    def test_generated_hashes_cover_every_generated_file(self) -> None:
        for adds_per_tick in (ADDS_PER_TICK, 20_000):
            self.assertEqual(
                set(generated_hashes(adds_per_tick)),
                set(generated_files(adds_per_tick)),
            )


if __name__ == "__main__":
    unittest.main()
