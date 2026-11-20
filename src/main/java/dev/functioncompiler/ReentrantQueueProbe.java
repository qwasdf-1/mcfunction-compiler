package dev.functioncompiler;

import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;

import java.util.concurrent.atomic.LongAdder;

/**
 * IR-013 disposable native parity adversary. A synchronous scoreboard
 * callback queues a real Minecraft function while the triggering score
 * mutation is running, using the SAME ExecutionContext as that command.
 *
 * The source program and all four native arms see the same injected work.
 * This does not register a normal gameplay callback and is disabled unless
 * FC_TYPED_IR_REENTRANT_TEST_OBSERVER=true.
 */
public final class ReentrantQueueProbe {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_REENTRANT_TEST_OBSERVER"));
    private static final Identifier INJECTED_FUNCTION =
            Identifier.fromNamespaceAndPath("fc_ir", "ir013_injected");
    private static final LongAdder INJECTIONS = new LongAdder();

    private ReentrantQueueProbe() {}

    public static void scoreChanged(
            MinecraftServer server, ScoreHolder owner, Objective objective
    ) {
        if (!ENABLED
                || !"#ir013_trigger".equals(owner.getScoreboardName())
                || !"fc_ir".equals(objective.getName())) {
            return;
        }
        ExecutionContext<CommandSourceStack> context = ExecutionContextBridge.currentContext();
        if (context == null) return;
        var target = server.getFunctions().get(INJECTED_FUNCTION);
        if (target.isEmpty()) {
            throw new IllegalStateException("IR013 test function is missing: " + INJECTED_FUNCTION);
        }
        try {
            CommandSourceStack source = server.createCommandSourceStack()
                    .withSuppressedOutput()
                    .withCallback(CommandResultCallback.EMPTY);
            var function = target.get().instantiate(null, source.dispatcher());
            // A real vanilla function-call queue action; do NOT run it
            // synchronously from the listener. Re-entrant queue ordering is
            // the observable effect under test.
            ExecutionContext.queueInitialFunctionCall(
                    context, function, source, CommandResultCallback.EMPTY);
            INJECTIONS.increment();
        } catch (Exception error) {
            throw new IllegalStateException("IR013 native reentrant injection failed", error);
        }
    }

    public static String diagnostics() {
        return " reentrant_test_injections=" + INJECTIONS.sum();
    }
}
