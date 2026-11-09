"""Tests for the Spark time-share attribution analyzer.

The analyzer's job is to partition sampled self weight across command families
without double counting. These tests pin the boundaries that matter for the
coverage-widening decision: macro argument construction must not be counted as a
``data`` command, a function body must be attributed to its own commands rather
than the call site, and runtime fork state must reach leaf commands.
"""

from __future__ import annotations

import unittest

from scripts.attribute_specialization_share import (
    StackNode,
    attribute_nodes,
    generic_family,
    is_fork_frame,
    is_idle_frame,
    is_macro_argument_frame,
    leaf_family,
)


def node(
    index: int,
    class_name: str,
    method_name: str = "run",
    weight: float = 1.0,
    children: list[int] | None = None,
) -> StackNode:
    return StackNode(
        index=index,
        class_name=class_name,
        method_name=method_name,
        weight=weight,
        children=children or [],
    )


class FamilyTests(unittest.TestCase):
    def test_nested_scoreboard_classes_are_scoreboard(self) -> None:
        for class_name in (
            "net.minecraft.server.commands.ScoreboardCommand",
            "net.minecraft.server.commands.ScoreboardCommand$2",
            "net.minecraft.server.commands.ScoreboardCommand$$Lambda.0x000000000f1872d8",
        ):
            with self.subTest(class_name=class_name):
                self.assertEqual(leaf_family(class_name), "scoreboard")

    def test_data_command_classes_are_data(self) -> None:
        for class_name in (
            "net.minecraft.server.commands.DataCommands",
            "net.minecraft.server.commands.DataCommands$Get",
            "net.minecraft.server.commands.data.EntityDataAccessor",
        ):
            with self.subTest(class_name=class_name):
                self.assertEqual(leaf_family(class_name), "data")

    def test_function_and_return_are_leaves(self) -> None:
        self.assertEqual(
            leaf_family("net.minecraft.server.commands.FunctionCommand$2"),
            "function-call",
        )
        self.assertEqual(
            leaf_family("net.minecraft.server.commands.ReturnCommand"), "return"
        )

    def test_generic_families(self) -> None:
        cases = {
            "dev.functioncompiler.FusedRegionPrototype": "compiler",
            "net.minecraft.server.ServerFunctionManager": "function-manager",
            "net.minecraft.commands.functions.MacroFunction": "macro",
            "net.minecraft.server.commands.ExecuteCommand": "execute",
            "net.minecraft.commands.execution.ExecutionContext": "command-queue",
            "com.mojang.brigadier.CommandDispatcher": "brigadier",
        }
        for class_name, expected in cases.items():
            with self.subTest(class_name=class_name):
                self.assertEqual(generic_family(class_name), expected)

    def test_macro_argument_frame_detection(self) -> None:
        self.assertTrue(
            is_macro_argument_frame(
                "net.minecraft.server.commands.FunctionCommand$2", "arguments"
            )
        )
        self.assertTrue(
            is_macro_argument_frame(
                "net.minecraft.server.commands.FunctionCommand", "getArgumentTag"
            )
        )
        self.assertFalse(
            is_macro_argument_frame(
                "net.minecraft.server.commands.FunctionCommand", "queueFunctions"
            )
        )
        self.assertFalse(
            is_macro_argument_frame("com.example.Thing", "arguments")
        )
        self.assertTrue(
            is_fork_frame(
                "net.minecraft.commands.execution.tasks.ContinuationTask"
            )
        )

    def test_idle_frames(self) -> None:
        self.assertTrue(
            is_idle_frame("libc.so.6", "__syscall_cancel_arch_end")
        )
        self.assertTrue(is_idle_frame("java.lang.Thread", "sleep"))
        self.assertTrue(is_idle_frame("jdk.internal.misc.Unsafe", "park"))
        self.assertFalse(is_idle_frame("java.util.HashMap", "putVal"))


class AttributionTests(unittest.TestCase):
    def test_self_weights_partition_the_tree(self) -> None:
        nodes = [
            node(0, "net.minecraft.server.MinecraftServer", "tick", weight=10.0, children=[1]),
            node(1, "net.minecraft.server.commands.DataCommands", "getData", weight=10.0),
        ]
        result = attribute_nodes(nodes, [0])
        self.assertEqual(result["total_self_weight"], 10.0)
        self.assertAlmostEqual(
            sum(result["family_self"].values()), result["total_self_weight"]
        )

    def test_data_command_is_data(self) -> None:
        nodes = [
            node(0, "net.minecraft.server.commands.DataCommands", "getData", weight=5.0)
        ]
        result = attribute_nodes(nodes, [0])
        self.assertEqual(result["family_self"], {"data": 5.0})

    def test_macro_argument_helper_is_not_a_data_command(self) -> None:
        nodes = [
            node(
                0,
                "net.minecraft.server.commands.FunctionCommand$2",
                "arguments",
                weight=8.0,
                children=[1],
            ),
            node(
                1,
                "net.minecraft.server.commands.FunctionCommand",
                "getArgumentTag",
                weight=8.0,
                children=[2],
            ),
            node(
                2,
                "net.minecraft.server.commands.DataCommands",
                "getSingleTag",
                weight=8.0,
            ),
        ]
        result = attribute_nodes(nodes, [0])
        self.assertEqual(result["family_self"], {"macro-argument": 8.0})

    def test_function_body_is_not_macro_argument(self) -> None:
        nodes = [
            node(
                0,
                "net.minecraft.server.commands.FunctionCommand",
                "queueFunctions",
                weight=10.0,
                children=[1],
            ),
            node(
                1,
                "net.minecraft.server.ServerFunctionManager",
                "execute",
                weight=10.0,
                children=[2],
            ),
            node(
                2,
                "net.minecraft.server.commands.DataCommands",
                "getData",
                weight=10.0,
            ),
        ]
        result = attribute_nodes(nodes, [0])
        self.assertEqual(result["family_self"]["function-call"], 0.0)
        self.assertEqual(result["family_self"]["function-manager"], 0.0)
        self.assertEqual(result["family_self"]["data"], 10.0)

    def test_fork_state_reaches_leaf_commands(self) -> None:
        nodes = [
            node(
                0,
                "net.minecraft.server.commands.ExecuteCommand",
                "execute",
                weight=6.0,
                children=[1],
            ),
            node(
                1,
                "net.minecraft.commands.execution.tasks.ContinuationTask",
                "schedule",
                weight=6.0,
                children=[2],
            ),
            node(
                2,
                "net.minecraft.server.commands.ScoreboardCommand",
                "lambda$register$1",
                weight=6.0,
            ),
        ]
        result = attribute_nodes(nodes, [0])
        self.assertEqual(result["family_forked_self"], {"scoreboard": 6.0})

    def test_idle_time_is_its_own_family(self) -> None:
        nodes = [
            node(
                0,
                "libc.so.6",
                "__syscall_cancel_arch_end",
                weight=6.0,
            ),
            node(
                1,
                "net.minecraft.server.commands.DataCommands",
                "getData",
                weight=4.0,
            ),
        ]
        result = attribute_nodes(nodes, [0, 1])
        self.assertEqual(result["family_self"], {"idle": 6.0, "data": 4.0})

    def test_inclusive_uses_topmost_family_segment(self) -> None:
        nodes = [
            node(
                0,
                "net.minecraft.server.ServerFunctionManager",
                "execute",
                weight=10.0,
                children=[1],
            ),
            node(
                1,
                "net.minecraft.server.commands.DataCommands",
                "getData",
                weight=10.0,
                children=[2],
            ),
            node(2, "java.util.HashMap", "putVal", weight=4.0),
        ]
        result = attribute_nodes(nodes, [0])
        self.assertEqual(result["family_inclusive"]["function-manager"], 10.0)
        self.assertEqual(result["family_inclusive"]["data"], 10.0)
        self.assertAlmostEqual(
            sum(result["family_self"].values()), result["total_self_weight"]
        )


if __name__ == "__main__":
    unittest.main()
