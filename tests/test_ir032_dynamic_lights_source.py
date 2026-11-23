"""IR-032 exact pack overlay, singular 26.3 paths, and recurring tick graph tests."""
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_ir032_dynamic_lights_source import (
    build_reachable,
    logical_pack_files,
    parse_functions,
    selected_overlays,
)


class IR032DynamicLightsSourceTests(unittest.TestCase):
    def test_selects_all_applicable_26_3_overlays_in_declared_order(self):
        meta = {
            "overlays": {"entries": [
                {"directory": "pack_1_21_6", "formats": {
                    "min_inclusive": 80, "max_inclusive": 121}},
                {"directory": "pack_26_2", "formats": {
                    "min_inclusive": 105, "max_inclusive": 120}},
                {"directory": "pack_26_3", "formats": {
                    "min_inclusive": 121, "max_inclusive": 121}},
            ]}
        }
        self.assertEqual(
            selected_overlays(meta), ["pack_1_21_6", "pack_26_3"])

    def test_rejects_missing_26_3_overlay(self):
        meta = {"overlays": {"entries": [
            {"directory": "pack_26_2", "formats": {
                "min_inclusive": 105, "max_inclusive": 120}},
        ]}}
        with self.assertRaisesRegex(AssertionError, "No Minecraft"):
            selected_overlays(meta)

    def test_selected_overlay_replaces_base_function(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("data/test/function/a.mcfunction", "say base\n")
            archive.writestr("pack_26_3/data/test/function/a.mcfunction", "say overlay\n")
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            files = logical_pack_files(archive, ["pack_1_21_6", "pack_26_3"])
        self.assertEqual(files["data/test/function/a.mcfunction"][1], b"say overlay\n")
        self.assertEqual(files["data/test/function/a.mcfunction"][0], 1)

    def test_prefers_singular_26_3_paths_over_legacy_plural(self):
        files = {
            "data/test/functions/work.mcfunction": (
                0, b"say legacy\n", "data/test/functions/work.mcfunction"),
            "data/test/function/work.mcfunction": (
                0, b"say current\n", "data/test/function/work.mcfunction"),
        }
        functions, _ = parse_functions(files)
        self.assertEqual(functions["test:work"]["command_preview"], ["say current"])

    def test_schedule_inside_execute_is_not_a_direct_function_call(self):
        files = {
            "data/test/function/tick.mcfunction": (
                0, b"execute unless score #x obj matches 0 run schedule function test:tick 1t\n",
                "data/test/function/tick.mcfunction"),
        }
        functions, _ = parse_functions(files)
        row = functions["test:tick"]
        self.assertEqual(row["scheduled_calls"], ["test:tick"])
        self.assertEqual(row["function_calls"], [])

    def test_reachable_graph_follows_load_schedule_and_function_tag(self):
        files = {
            "data/test/function/load.mcfunction": (
                0, b"schedule function test:tickcheck 1t\n",
                "data/test/function/load.mcfunction"),
            "data/test/function/tickcheck.mcfunction": (
                0, b"execute unless score #x obj matches 0 run schedule function test:tickcheck 1t\n"
                   b"function test:tick\n",
                "data/test/function/tickcheck.mcfunction"),
            "data/test/function/tick.mcfunction": (
                0, b"function #test:hook\n",
                "data/test/function/tick.mcfunction"),
            "data/test/function/work.mcfunction": (
                0, b"scoreboard players add #x obj 1\n",
                "data/test/function/work.mcfunction"),
            "data/minecraft/tags/function/load.json": (
                0, json.dumps({"values": ["test:load"]}).encode(),
                "data/minecraft/tags/function/load.json"),
            "data/test/tags/function/hook.json": (
                0, json.dumps({"values": ["test:work"]}).encode(),
                "data/test/tags/function/hook.json"),
        }
        functions, tags = parse_functions(files)
        graph = build_reachable(functions, tags)
        self.assertEqual(set(graph["reachable_functions"]), {
            "test:load", "test:tickcheck", "test:tick", "test:work",
        })
        self.assertIn(
            {"from": "test:tickcheck", "to": "test:tickcheck"},
            graph["recurring_schedule_edges"],
        )
        self.assertEqual(graph["unresolved_function_tags"], [])


if __name__ == "__main__":
    unittest.main()
