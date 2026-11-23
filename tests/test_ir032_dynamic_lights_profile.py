"""IR-032 Dynamic Lights runtime census parsing and conservation tests."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "runtime"))

from run_dynamic_lights_profile import (
    ADVANCE_TIME_GAMERULE,
    SPAWN_MOBS_GAMERULE,
    assert_compiler_research_features_disabled,
    configure_gradle_cache_environment,
    disable_and_verify_gamerule,
    parse_exec_census_lines,
)


VALID_LOG = [
    "INFO FC_EXEC_BEGIN namespace=test sites=2 entries=5 callbacks=3 overflow=0 targets=2 callees=2 native_calls=3 single_dispatch_entries=3 complex_dispatch_entries=0",
    "INFO FC_EXEC_ROW function=test:tick index=0 entries=2 callbacks=1 kind=ordinary_callback dispatch_shape=none input=scoreboard players add #x obj 1",
    "INFO FC_EXEC_ROW function=test:tick index=1 entries=3 callbacks=2 kind=ordinary_callback dispatch_shape=single_score_static_call input=execute if score #x obj matches 1 run function test:child",
    "INFO FC_EXEC_CALLEE function=test:child native_call_tasks=2",
    "INFO FC_EXEC_CALLEE function=test:tick native_call_tasks=1",
    "INFO FC_EXEC_END namespace=test sites=2 entries=5 callbacks=3 overflow=0 native_calls=3 single_dispatch_entries=3 complex_dispatch_entries=0",
]


class IR032DynamicLightsProfileTests(unittest.TestCase):
    def test_minecraft_26_3_game_rules_are_namespaced_and_read_back_false(self):
        self.assertEqual(ADVANCE_TIME_GAMERULE, "minecraft:advance_time")
        self.assertEqual(SPAWN_MOBS_GAMERULE, "minecraft:spawn_mobs")

        class Rcon:
            def __init__(self):
                self.commands = []

            def command(self, cmd):
                self.commands.append(cmd)
                if cmd.endswith(" false"):
                    return "Gamerule changed"
                return f"Gamerule {cmd.split(' ')[1]} is currently set to false"

        server = Rcon()
        for rule in (ADVANCE_TIME_GAMERULE, SPAWN_MOBS_GAMERULE):
            result = disable_and_verify_gamerule(server, rule)
            self.assertEqual(result["rule"], rule)
            self.assertIn("false", result["query_response"])
        self.assertEqual(server.commands, [
            "gamerule minecraft:advance_time false",
            "gamerule minecraft:advance_time",
            "gamerule minecraft:spawn_mobs false",
            "gamerule minecraft:spawn_mobs",
        ])

    def test_minecraft_26_3_game_rule_rejects_legacy_name(self):
        with self.assertRaisesRegex(ValueError, "Unexpected Minecraft 26.3 gamerule"):
            disable_and_verify_gamerule(object(), "doMobSpawning")

    def test_minecraft_26_3_game_rule_rejects_failed_or_true_readback(self):
        class Rcon:
            def __init__(self, final):
                self.final = final

            def command(self, cmd):
                if cmd.endswith(" false"):
                    return "Incorrect argument for command"
                return self.final

        for response in (
            "Incorrect argument for command",
            "Gamerule minecraft:spawn_mobs is currently set to true",
            "false positives are not an exact false readback",
        ):
            with self.subTest(response=response):
                with self.assertRaisesRegex(RuntimeError, "did not read back as false"):
                    disable_and_verify_gamerule(Rcon(response), SPAWN_MOBS_GAMERULE)

    def test_parses_and_reconciles_exact_census(self):
        report = parse_exec_census_lines(VALID_LOG, "test")
        self.assertEqual(report["summary"]["sites"], 2)
        self.assertEqual(report["summary"]["entries"], 5)
        self.assertEqual(report["summary"]["callbacks"], 3)
        self.assertEqual(report["summary"]["native_calls"], 3)
        self.assertEqual(report["per_function"]["test:tick"], {
            "sites": 2,
            "active_sites": 2,
            "entries": 5,
            "callbacks": 3,
            "active_callback_sites": 2,
        })
        self.assertEqual(report["callee_rows"], [
            {"function": "test:child", "native_call_tasks": 2},
            {"function": "test:tick", "native_call_tasks": 1},
        ])

    def test_rejects_missing_summary_boundary(self):
        with self.assertRaisesRegex(ValueError, "Expected one FC_EXEC_BEGIN"):
            parse_exec_census_lines(VALID_LOG[:-1], "test")

    def test_rejects_wrong_namespace(self):
        with self.assertRaisesRegex(ValueError, "namespace mismatch"):
            parse_exec_census_lines(VALID_LOG, "other")

    def test_rejects_site_row_count_mismatch(self):
        altered = [line for line in VALID_LOG if "FC_EXEC_ROW " not in line]
        with self.assertRaisesRegex(ValueError, "site conservation"):
            parse_exec_census_lines(altered, "test")

    def test_rejects_entry_counter_mismatch(self):
        altered = [
            line.replace("entries=5", "entries=6")
            if "FC_EXEC_END " in line else line
            for line in VALID_LOG
        ]
        with self.assertRaisesRegex(ValueError, "BEGIN/END mismatch"):
            parse_exec_census_lines(altered, "test")

    def test_gradle_cache_helper_removes_same_writable_readonly_path(self):
        environment = {
            "GRADLE_USER_HOME": "/tmp/gradle-home",
            "GRADLE_RO_DEP_CACHE": "/tmp/gradle-home/caches",
        }
        configured = configure_gradle_cache_environment(environment)
        self.assertNotIn("GRADLE_RO_DEP_CACHE", configured)
        self.assertEqual(environment["GRADLE_RO_DEP_CACHE"], "/tmp/gradle-home/caches")

    def test_gradle_cache_helper_preserves_distinct_readonly_cache(self):
        environment = {
            "GRADLE_USER_HOME": "/tmp/gradle-home",
            "GRADLE_RO_DEP_CACHE": "/tmp/readonly-gradle-cache",
        }
        configured = configure_gradle_cache_environment(environment)
        self.assertEqual(
            configured["GRADLE_RO_DEP_CACHE"], "/tmp/readonly-gradle-cache"
        )

    def test_research_feature_gate_accepts_all_disabled_status(self):
        status = " ".join(
            f"{name}=false"
            for name in (
                "score_add_prototype_enabled",
                "score_add_metrics_enabled",
                "score_add_timing_enabled",
                "score_add_attr_enabled",
                "score_attr_diag_enabled",
                "fused_region_prototype_enabled",
                "direct_scheduler_prototype_enabled",
                "direct_scheduler_diagnostics_enabled",
                "bytecode_region_prototype_enabled",
                "bytecode_compile_failure_forced",
                "arch_counters_enabled",
                "ir030_pos_get_enabled",
                "ir030_pos_get_verify",
                "function_timing_enabled",
                "command_callback_metrics_enabled",
                "command_callback_metrics_all_queues",
                "selective_macro_arguments_enabled",
                "selective_macro_arguments_metrics_enabled",
            )
        )
        assert_compiler_research_features_disabled(status)

    def test_research_feature_gate_rejects_enabled_optimizer(self):
        status = " ".join(
            f"{name}={'true' if name == 'fused_region_prototype_enabled' else 'false'}"
            for name in (
                "score_add_prototype_enabled",
                "score_add_metrics_enabled",
                "score_add_timing_enabled",
                "score_add_attr_enabled",
                "score_attr_diag_enabled",
                "fused_region_prototype_enabled",
                "direct_scheduler_prototype_enabled",
                "direct_scheduler_diagnostics_enabled",
                "bytecode_region_prototype_enabled",
                "bytecode_compile_failure_forced",
                "arch_counters_enabled",
                "ir030_pos_get_enabled",
                "ir030_pos_get_verify",
                "function_timing_enabled",
                "command_callback_metrics_enabled",
                "command_callback_metrics_all_queues",
                "selective_macro_arguments_enabled",
                "selective_macro_arguments_metrics_enabled",
            )
        )
        with self.assertRaisesRegex(RuntimeError, "fused_region_prototype_enabled=false"):
            assert_compiler_research_features_disabled(status)

    def test_rejects_registration_overflow(self):
        altered = [
            line.replace("overflow=0", "overflow=1")
            if "FC_EXEC_BEGIN " in line or "FC_EXEC_END " in line else line
            for line in VALID_LOG
        ]
        with self.assertRaisesRegex(ValueError, "registration overflow"):
            parse_exec_census_lines(altered, "test")


if __name__ == "__main__":
    unittest.main()
