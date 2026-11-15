"""Contract tests for SCHED-ATTR-001's profiler classification.

These checks intentionally do not require a running Minecraft server or JFR.
They guard the two mistakes found in the first screening run: JVM slash names
must normalize to dotted names, and probe tracing must not be attributed to
the vanilla queue.
"""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ci_scheduler_attribution import classify_stack, describe_frame  # noqa: E402


class SchedulerAttributionTests(unittest.TestCase):
    def test_jfr_internal_name_normalization(self) -> None:
        frame = {
            "method": {
                "type": {"name": "net/minecraft/commands/execution/ExecutionContext"},
                "name": "runCommandQueue",
            }
        }
        self.assertEqual(
            describe_frame(frame),
            "net.minecraft.commands.execution.ExecutionContext.runCommandQueue",
        )

    def test_disabled_trace_env_lookup_is_not_vanilla_scheduler(self) -> None:
        self.assertEqual(
            classify_stack([
                "java.lang.ProcessEnvironment.getenv",
                "dev.functioncompiler.ProbeConfiguration.readBoolean",
                "dev.functioncompiler.ProbeConfiguration.traceEnabled",
                "net.minecraft.commands.execution.ExecutionContext.runCommandQueue",
            ]),
            "compiler_probe_env_lookup",
        )

    def test_queue_layer_stays_a_separate_class(self) -> None:
        self.assertEqual(
            classify_stack([
                "net.minecraft.commands.execution.ExecutionContext.pushNewCommands",
                "net.minecraft.commands.execution.ExecutionContext.runCommandQueue",
            ]),
            "scheduler_or_function_queue",
        )

    def test_scoreboard_work_not_counted_as_scheduler(self) -> None:
        self.assertEqual(
            classify_stack([
                "java.util.HashMap.get",
                "net.minecraft.world.scores.Scoreboard.getOrCreatePlayerScore",
                "com.mojang.brigadier.context.ContextChain.runExecutable",
                "net.minecraft.commands.execution.ExecutionContext.runCommandQueue",
            ]),
            "scoreboard_operation",
        )

    def test_fabric_event_hooks_are_attributed_separately(self) -> None:
        self.assertEqual(
            classify_stack([
                "java.lang.ThreadLocal.get",
                "net.fabricmc.fabric.impl.entity.event.effect.MobEffectUtil.popContext",
                "com.mojang.brigadier.context.ContextChain.runExecutable",
                "net.minecraft.commands.execution.ExecutionContext.runCommandQueue",
            ]),
            "fabric_entity_event_hook",
        )


if __name__ == "__main__":
    unittest.main()
