"""IR-032 moving-source and exact execution-census parser tests."""
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_ir032_dynamic_lights_census import (
    NAMESPACE, TARGETS, parse_exec_census,
    verify_clean_minecraft_26_3_environment,
)
from run_dynamic_lights_profile import (
    MOVING_MIN_DISPLACEMENT_BLOCKS,
    STATIONARY_MAX_DISPLACEMENT_BLOCKS,
    assert_clean_dynamic_lights_population,
    assert_item_motion_scenario,
    data_modify_succeeded,
    entity_position,
    item_motion,
    purge_post_warmup_non_fixture_items,
    summarize_item_displacements,
)


class FakeRcon:
    def __init__(self, response):
        self.response = response

    def command(self, command):
        self.command_seen = command
        return self.response


class IR032DynamicLightsRunnerTests(unittest.TestCase):
    def test_entity_position_parses_snbt_doubles(self):
        rcon = FakeRcon("The data of entity abc is [1.25d, 65.0d, -2.5d]")
        self.assertEqual(entity_position(rcon, 7), (1.25, 65.0, -2.5))
        self.assertIn("tag=fc_dl_7", rcon.command_seen)

    def test_entity_position_rejects_missing_entity(self):
        with self.assertRaisesRegex(RuntimeError, "Could not parse position"):
            entity_position(FakeRcon("No entity was found"), 0)

    def test_motion_reset_accepts_modified_and_already_zero_responses(self):
        self.assertTrue(data_modify_succeeded("Modified entity data of 1 entity"))
        self.assertTrue(data_modify_succeeded(
            "Nothing changed. The specified properties already have these values"
        ))
        self.assertFalse(data_modify_succeeded("No entity was found"))

    def clean_source_population(self):
        return {
            "item_entities": 24,
            "holder_entities": 4,
            "holder_entities_by_type": {
                "players": 4, "zombies": 0, "husks": 0, "foxes": 0,
                "zombie_villagers": 0, "allays": 0,
            },
            "other_light_sources": {
                "on_fire": 0, "tnt": 0, "glowing": 0,
                "glow_squids": 0, "allays": 0, "enchanted_armor": 0,
            },
        }

    def test_post_warmup_cleanup_only_targets_untagged_drops(self):
        rcon = FakeRcon("Killed 14 entities")
        with patch("run_dynamic_lights_profile.count_entities", side_effect=[14, 0]) as counts:
            result = purge_post_warmup_non_fixture_items(rcon, "fc_test")
        self.assertEqual(result["untracked_items_removed_before_measurement"], 14)
        self.assertEqual(result["untracked_items_remaining"], 0)
        self.assertEqual(rcon.command_seen, "kill @e[type=minecraft:item,tag=!fc_dl]")
        self.assertEqual(counts.call_count, 2)
        self.assertTrue(result["cleanup_only_before_measurement"])

    def test_post_warmup_cleanup_skips_kill_when_clean(self):
        rcon = FakeRcon("No entity was found")
        with patch("run_dynamic_lights_profile.count_entities", side_effect=[0, 0]):
            result = purge_post_warmup_non_fixture_items(rcon, "fc_test")
        self.assertIsNone(result["kill_response"])
        self.assertEqual(result["untracked_items_removed_before_measurement"], 0)
        self.assertFalse(hasattr(rcon, "command_seen"))

    def test_post_warmup_cleanup_rejects_remaining_stray_items(self):
        rcon = FakeRcon("Killed 14 entities")
        with patch("run_dynamic_lights_profile.count_entities", side_effect=[14, 1]):
            with self.assertRaisesRegex(RuntimeError, "Untracked dropped items remain"):
                purge_post_warmup_non_fixture_items(rcon, "fc_test")

    def test_clean_source_population_accepts_only_fixture_players_and_torches(self):
        assert_clean_dynamic_lights_population(self.clean_source_population())

    def test_clean_source_population_rejects_extra_holder_mobs(self):
        population = self.clean_source_population()
        population["holder_entities"] = 5
        population["holder_entities_by_type"]["zombies"] = 1
        with self.assertRaisesRegex(RuntimeError, "uncontrolled holder entities"):
            assert_clean_dynamic_lights_population(population)

    def test_clean_source_population_rejects_other_light_sources(self):
        population = self.clean_source_population()
        population["other_light_sources"]["on_fire"] = 1
        with self.assertRaisesRegex(RuntimeError, "non-torch light sources"):
            assert_clean_dynamic_lights_population(population)

    def test_clean_source_population_rejects_extra_dropped_items(self):
        population = self.clean_source_population()
        population["item_entities"] = 25
        with self.assertRaisesRegex(RuntimeError, "exactly 24 dropped items"):
            assert_clean_dynamic_lights_population(population)

    def test_motion_vectors_keep_each_source_near_its_player(self):
        vectors = [item_motion(index) for index in range(24)]
        self.assertEqual(len(vectors), 24)
        self.assertEqual(vectors[0], (0.35, 0.12))
        self.assertEqual(vectors[8], (-0.35, 0.12))
        self.assertEqual(vectors[12], (0.35, -0.12))
        self.assertEqual(vectors[20], (-0.35, -0.12))

    def test_stationary_control_accepts_observed_subquarter_block_drift(self):
        summary = summarize_item_displacements({
            index: (0.0692449 if index == 7 else 0.0198)
            for index in range(24)
        })
        self.assertEqual(summary["moved_item_count"], 0)
        self.assertAlmostEqual(summary["maximum_displacement_blocks"], 0.0692449)
        self.assertEqual(summary["stationary_max_displacement_blocks"], 0.25)
        assert_item_motion_scenario(summary, "stationary")

    def test_stationary_control_rejects_quarter_block_or_greater_drift(self):
        summary = summarize_item_displacements({
            index: (0.250001 if index == 7 else 0.0198)
            for index in range(24)
        })
        with self.assertRaisesRegex(RuntimeError, "quarter-block drift bound"):
            assert_item_motion_scenario(summary, "stationary")

    def test_moving_control_requires_every_source_to_move_at_least_one_block(self):
        summary = summarize_item_displacements({index: 1.0 for index in range(24)})
        self.assertEqual(summary["moved_item_count"], 24)
        self.assertEqual(summary["moving_min_displacement_blocks"], 1.0)
        assert_item_motion_scenario(summary, "moving")

    def test_moving_control_rejects_any_source_below_one_block(self):
        distances = {index: 1.01 for index in range(24)}
        distances[9] = 0.999
        summary = summarize_item_displacements(distances)
        with self.assertRaisesRegex(RuntimeError, "did not move every item"):
            assert_item_motion_scenario(summary, "moving")

    def test_displacement_summary_rejects_empty_or_invalid_samples(self):
        with self.assertRaisesRegex(ValueError, "No Dynamic Lights"):
            summarize_item_displacements({})
        with self.assertRaisesRegex(ValueError, "Invalid Dynamic Lights"):
            summarize_item_displacements({0: float("nan")})
        with self.assertRaisesRegex(ValueError, "Invalid Dynamic Lights"):
            summarize_item_displacements({0: -0.01})


class IR032EnvironmentGateTests(unittest.TestCase):
    def example_manifest(self):
        population = {
            "item_entities": 24,
            "holder_entities": 4,
            "holder_entities_by_type": {
                "players": 4, "zombies": 0, "husks": 0, "foxes": 0,
                "zombie_villagers": 0, "allays": 0,
            },
            "other_light_sources": {
                "on_fire": 0, "tnt": 0, "glowing": 0, "glow_squids": 0,
                "allays": 0, "enchanted_armor": 0,
            },
        }
        return {
            "mob_spawning_gamerule_status": {
                "rule": "minecraft:spawn_mobs",
                "set_response": "Gamerule changed",
                "query_response": "Gamerule minecraft:spawn_mobs is set to false",
            },
            "daylight_gamerule_status": {
                "rule": "minecraft:advance_time",
                "set_response": "Gamerule changed",
                "query_response": "Gamerule minecraft:advance_time is set to false",
            },
            "source_population_before_profile": population,
            "source_population_after_profile": {
                **population,
                "other_light_sources": dict(population["other_light_sources"]),
                "holder_entities_by_type": dict(population["holder_entities_by_type"]),
            },
        }

    def test_accepts_both_current_gamerules_and_clean_matched_populations(self):
        result = verify_clean_minecraft_26_3_environment(self.example_manifest())
        self.assertTrue(result["pre_and_post_source_population_verified"])
        self.assertTrue(result["minecraft_26_3_spawn_mobs_disabled"])

    def test_rejects_legacy_gamerule_or_true_readback(self):
        for invalid in ("doMobSpawning", "minecraft:spawn_mobs_old"):
            case = self.example_manifest()
            case["mob_spawning_gamerule_status"]["rule"] = invalid
            with self.assertRaisesRegex(AssertionError, "Unverified Minecraft"):
                verify_clean_minecraft_26_3_environment(case)
        case = self.example_manifest()
        case["daylight_gamerule_status"]["query_response"] = "Gamerule is set to true"
        with self.assertRaisesRegex(AssertionError, "Unverified Minecraft"):
            verify_clean_minecraft_26_3_environment(case)

    def test_rejects_cleanliness_drift_before_or_after_profile(self):
        for label in ("source_population_before_profile", "source_population_after_profile"):
            case = self.example_manifest()
            case[label]["other_light_sources"]["on_fire"] = 1
            with self.assertRaisesRegex(AssertionError, "Unexpected other light source"):
                verify_clean_minecraft_26_3_environment(case)
        case = self.example_manifest()
        case["source_population_after_profile"]["holder_entities"] = 5
        with self.assertRaisesRegex(AssertionError, "Uncontrolled source/holder"):
            verify_clean_minecraft_26_3_environment(case)


class IR032ExecutionCensusParserTests(unittest.TestCase):
    def sample_log(self):
        rows = []
        for index, target in enumerate(TARGETS):
            rows.append(
                f"FC_EXEC_ROW function={NAMESPACE}:{target} index=0 "
                "entries=3 callbacks=3 kind=plain dispatch_shape=normal input=none"
            )
        return [
            f"FC_EXEC_BEGIN namespace={NAMESPACE} sites={len(TARGETS)} "
            "entries=45 callbacks=45 overflow=0 "
            f"targets={len(TARGETS)} callees=2 native_calls=10",
            *rows,
            f"FC_EXEC_CALLEE function={NAMESPACE}:internal/tick native_call_tasks=4",
            f"FC_EXEC_CALLEE function={NAMESPACE}:internal/tickcheck native_call_tasks=6",
            f"FC_EXEC_END namespace={NAMESPACE} entries=45 callbacks=45 native_calls=10",
        ]

    def test_reconciles_all_target_sites_and_callee_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "census.log"
            path.write_text("\n".join(self.sample_log()), encoding="utf-8")
            result = parse_exec_census(
                path,
                [f"{NAMESPACE}:internal/tick", f"{NAMESPACE}:internal/tickcheck"],
            )
        self.assertEqual(result["summary"]["sites"], str(len(TARGETS)))
        self.assertEqual(result["total_function_call_tasks"], 10)
        self.assertEqual(set(result["target_functions_observed"]),
                         {f"{NAMESPACE}:{target}" for target in TARGETS})

    def test_rejects_unreconciled_native_call_count(self):
        lines = self.sample_log()
        lines[-2] = f"FC_EXEC_CALLEE function={NAMESPACE}:internal/tickcheck native_call_tasks=5"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "census.log"
            path.write_text("\n".join(lines), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "do not reconcile"):
                parse_exec_census(
                    path,
                    [f"{NAMESPACE}:internal/tick", f"{NAMESPACE}:internal/tickcheck"],
                )


if __name__ == "__main__":
    unittest.main()
