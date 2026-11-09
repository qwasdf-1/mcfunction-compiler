"""Tests for the H2-first specialization inventory.

The inventory's classification must match the compiler's real eligibility
rules, so these tests pin the pure pieces: execute-chain fork detection, leaf
family mapping, pure-leaf inlining, adjacent-run counting, and pack
reachability including the self-rescheduling tick loop Dynamic Lights uses.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.run_specialization_inventory import (
    FAKE_HOLDER_ADD,
    Pack,
    adjacent_runs,
    is_pure_leaf,
    leaf_family,
    normalize_command_line,
    parse_execute,
    split_tokens,
    summarize_pack,
)


class TokenizerTests(unittest.TestCase):
    def test_bracketed_and_quoted_text_stays_one_token(self) -> None:
        tokens = split_tokens('execute as @e[tag=as,name="a b"] run say hi')
        self.assertEqual(tokens[:3], ["execute", "as", "@e[tag=as,name=\"a b\"]"])
        self.assertEqual(tokens[-2:], ["say", "hi"])

    def test_escaped_quote_does_not_end_the_string(self) -> None:
        tokens = split_tokens('say "a \\" b" c')
        self.assertEqual(tokens, ["say", '"a \\" b"', "c"])


class ExecuteClassificationTests(unittest.TestCase):
    def test_as_forks(self) -> None:
        is_execute, forked, inner = parse_execute(
            "execute as @e[tag=x] run scoreboard players add #state demo 1"
        )
        self.assertTrue(is_execute)
        self.assertTrue(forked)
        self.assertEqual(inner, "scoreboard players add #state demo 1")

    def test_at_and_on_and_summon_fork(self) -> None:
        for line in (
            "execute at @s run scoreboard players set #x demo 1",
            "execute on vehicle run scoreboard players set #x demo 1",
            "execute summon minecraft:pig run scoreboard players set #x demo 1",
        ):
            with self.subTest(line=line):
                self.assertTrue(parse_execute(line)[1])

    def test_positioned_and_condition_do_not_fork(self) -> None:
        for line in (
            "execute positioned 0 0 0 run scoreboard players set #x demo 1",
            "execute if block ~ ~ ~ minecraft:stone run scoreboard players set #x demo 1",
            "execute store result score #x demo run data get entity @s Health",
        ):
            with self.subTest(line=line):
                is_execute, forked, inner = parse_execute(line)
                self.assertTrue(is_execute)
                self.assertFalse(forked)
                self.assertIsNotNone(inner)

    def test_condition_without_run_has_no_inner(self) -> None:
        self.assertEqual(
            parse_execute("execute if score #x demo matches 1.."), (True, False, None)
        )

    def test_plain_command_is_not_execute(self) -> None:
        self.assertEqual(
            parse_execute("scoreboard players add #state demo 1"), (False, False, None)
        )


class FamilyTests(unittest.TestCase):
    def test_macro_marker_is_not_part_of_the_command(self) -> None:
        self.assertEqual(
            normalize_command_line("$scoreboard players add #macro demo $(n)"),
            "scoreboard players add #macro demo $(n)",
        )
        self.assertEqual(
            normalize_command_line("  scoreboard players add #state demo 1  "),
            "scoreboard players add #state demo 1",
        )

    def test_leaf_families(self) -> None:
        cases = {
            "scoreboard players add #state demo 1": "score-add",
            "scoreboard players set #state demo 1": "score-store",
            "scoreboard players reset #state demo": "score-reset",
            "scoreboard players operation #a demo += #b demo": "score-operation",
            "data get entity @s Health": "data-get",
            "data modify storage demo:data value set value 1": "data-store",
            "data merge storage demo:data {x:1}": "data-storage",
            "return run function demo:leaf": "tail-call",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(leaf_family(command), expected)

    def test_non_leaf_commands(self) -> None:
        for command in ("say hi", "particle flame ~ ~ ~ 0 0 0 0 1", "execute run say hi"):
            with self.subTest(command=command):
                self.assertIsNone(leaf_family(command))

    def test_literal_fake_holder_adds_only(self) -> None:
        self.assertTrue(
            FAKE_HOLDER_ADD.match("scoreboard players add #head vmr.runtime 1")
        )
        self.assertFalse(
            FAKE_HOLDER_ADD.match("scoreboard players add @s vmr.runtime 1")
        )
        self.assertFalse(
            FAKE_HOLDER_ADD.match("scoreboard players set #head vmr.runtime 1")
        )


class PureLeafTests(unittest.TestCase):
    def test_short_leaf_function_is_inlinable(self) -> None:
        self.assertTrue(
            is_pure_leaf(
                [
                    "scoreboard players add #leaf demo 1",
                    "data modify storage demo:data value set value 1",
                ]
            )
        )

    def test_macro_function_is_not_inlinable(self) -> None:
        self.assertFalse(
            is_pure_leaf(["scoreboard players add #leaf demo $(n)"])
        )

    def test_nested_function_and_return_are_not_leaves(self) -> None:
        self.assertFalse(is_pure_leaf(["function demo:other"]))
        self.assertFalse(is_pure_leaf(["return run function demo:other"]))

    def test_too_long_is_not_a_leaf(self) -> None:
        self.assertFalse(is_pure_leaf(["say x"] * 65))


class AdjacentRunTests(unittest.TestCase):
    def test_maximal_runs_of_two_or_more(self) -> None:
        self.assertEqual(
            adjacent_runs([True, True, False, True, True, True, False, True]),
            {"count": 2, "commands": 5, "longest": 3},
        )

    def test_singletons_do_not_count(self) -> None:
        self.assertEqual(
            adjacent_runs([True, False, True]), {"count": 0, "commands": 0, "longest": 0}
        )


def write_synthetic_pack(directory: Path) -> Path:
    """A pack with a tick entry, a scheduled loop, a leaf, and a macro."""
    path = directory / "synthetic.zip"
    functions = {
        "demo:tick": "\n".join(
            [
                "scoreboard players set #state demo 0",
                "scoreboard players add #state demo 1",
                "execute as @e[tag=x] run scoreboard players add #state demo 1",
                "execute positioned 0 0 0 run data modify storage demo:data value set value 1",
                "execute if block ~ ~ ~ minecraft:stone run scoreboard players set #state demo 2",
                "function demo:leaf",
                "function demo:macro with storage demo:data",
            ]
        )
        + "\n",
        "demo:leaf": "scoreboard players add #leaf demo 1\n",
        "demo:macro": "$scoreboard players add #macro demo $(n)\n",
        "demo:load": "schedule function demo:scheduled 1t\n",
        "demo:scheduled": (
            "scoreboard players set #s demo 0\nscoreboard players set #s demo 1\n"
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "data/minecraft/tags/function/tick.json",
            json.dumps({"values": ["demo:tick"]}),
        )
        archive.writestr(
            "data/minecraft/tags/function/load.json",
            json.dumps({"values": ["demo:load"]}),
        )
        for function_id, text in functions.items():
            namespace, relative = function_id.split(":", 1)
            archive.writestr(f"data/{namespace}/function/{relative}.mcfunction", text)
    return path


class PackReachabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.pack_path = write_synthetic_pack(Path(self.temporary.name))
        self.pack = Pack("synthetic", self.pack_path, "unused")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_tick_and_load_entries_are_reachable(self) -> None:
        reachable = self.pack.reachable(("minecraft:tick", "minecraft:load"))
        self.assertEqual(
            reachable, {"demo:tick", "demo:leaf", "demo:macro", "demo:load", "demo:scheduled"}
        )

    def test_scheduled_loop_is_tick_work(self) -> None:
        scheduled = self.pack.scheduled_from(("minecraft:load",))
        self.assertEqual(scheduled, {"demo:scheduled"})

    def test_modern_function_path_wins_over_legacy_copy(self) -> None:
        path = Path(self.temporary.name) / "mixed.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "data/demo/function/tick.mcfunction",
                "scoreboard players set #modern demo 1\n",
            )
            archive.writestr(
                "data/demo/functions/tick.mcfunction",
                "scoreboard players set #legacy demo 1\n",
            )
        pack = Pack("mixed", path, "unused")
        self.assertEqual(
            pack.functions["demo:tick"], ["scoreboard players set #modern demo 1"]
        )

    def test_legacy_function_path_is_used_when_modern_is_absent(self) -> None:
        path = Path(self.temporary.name) / "legacy.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "data/demo/functions/tick.mcfunction",
                "scoreboard players set #legacy demo 1\n",
            )
        pack = Pack("legacy", path, "unused")
        self.assertEqual(
            pack.functions["demo:tick"], ["scoreboard players set #legacy demo 1"]
        )

    def test_summary_matches_the_expected_eligibility(self) -> None:
        summary = summarize_pack(self.pack)
        totals = summary["totals"]
        self.assertEqual(totals["functions_tick"], 4)  # tick, leaf, macro, scheduled
        self.assertEqual(totals["tick_forked_lines"], 1)
        # tick (2) + demo:leaf (1) + demo:macro body (1) + scheduled (2). The
        # macro body line's leading "$" is stripped before classification.
        self.assertEqual(totals["tick_leaf_lines"], 6)
        self.assertEqual(totals["tick_context_lines"], 2)
        self.assertEqual(totals["tick_adjacent_runs"], 3)
        self.assertEqual(totals["tick_adjacent_run_commands"], 7)
        self.assertEqual(totals["tick_macro_calls"], 1)
        self.assertEqual(totals["macro_functions"], 1)

        tick = summary["functions"]["demo:tick"]
        self.assertEqual(tick["inline_calls"], 1)  # demo:leaf only
        self.assertEqual(tick["macro_calls"], 1)


if __name__ == "__main__":
    unittest.main()
