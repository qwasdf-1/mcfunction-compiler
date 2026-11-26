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

    /**
     * Test-only IR-014 adversaries. Each watched holder queues a genuine
     * vanilla function call; none of the callbacks run the function inline.
     * A second watched holder supports a nested (cascading) queue insertion.
     */
    private static Identifier injectedFor(String holder) {
        String path = switch (holder) {
            case "#ir013_trigger" -> "ir013_injected";
            case "#ir014_chain" -> "ir014_inject_first";
            case "#ir014_second" -> "ir014_inject_second";
            case "#ir014_recreate" -> "ir014_inject_recreate";
            case "#ir014_drop" -> "ir014_inject_drop";
            case "#ir014_return" -> "ir014_inject_return";
            case "#fc046_queue" -> "ir017_ir046_injected";
            default -> null;
        };
        return path == null ? null : Identifier.fromNamespaceAndPath("fc_ir", path);
    }
    private static final LongAdder INJECTIONS = new LongAdder();

    private ReentrantQueueProbe() {}

    public static void scoreChanged(
            MinecraftServer server, ScoreHolder owner, Objective objective
    ) {
        if (!ENABLED || !"fc_ir".equals(objective.getName())) return;
        Identifier injected = injectedFor(owner.getScoreboardName());
        if (injected == null) return;
        ExecutionContext<CommandSourceStack> context = ExecutionContextBridge.currentContext();
        if (context == null) return;
        var target = server.getFunctions().get(injected);
        if (target.isEmpty()) {
            throw new IllegalStateException("Reentrant test function is missing: " + injected);
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
            throw new IllegalStateException("Reentrant native test injection failed", error);
        }
    }

    public static String diagnostics() {
        return " reentrant_test_injections=" + INJECTIONS.sum();
    }
}
