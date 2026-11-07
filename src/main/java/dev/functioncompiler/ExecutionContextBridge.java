package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;

import java.util.ArrayDeque;
import java.util.Deque;

import dev.functioncompiler.mixin.ExecutionContextAccessor;

public final class ExecutionContextBridge {
    private static final ThreadLocal<Deque<ExecutionContext<?>>> STACK =
            ThreadLocal.withInitial(ArrayDeque::new);

    private ExecutionContextBridge() {
    }

    public static void push(ExecutionContext<?> context) {
        STACK.get().push(context);
    }

    public static void pop() {
        Deque<ExecutionContext<?>> stack = STACK.get();
        if (!stack.isEmpty()) {
            stack.pop();
            if (stack.isEmpty()) {
                STACK.remove();
            }
        }
    }

    public static <T> ExecutionContext<T> currentContext() {
        Deque<ExecutionContext<?>> stack = STACK.get();
        if (stack.isEmpty()) {
            return null;
        }
        @SuppressWarnings("unchecked")
        ExecutionContext<T> context = (ExecutionContext<T>) stack.peek();
        return context;
    }

    /**
     * Charges vanilla's per-stage quota debit for inlined modifier stages.
     *
     * <p>Vanilla's {@code BuildContexts} charges {@code incrementCost()} once
     * per modifier stage that carries a redirect modifier, before that stage's
     * sources are resolved, and {@code ExecuteCommand} charges once per final
     * source. A compiled chain keeps the per-source debit (the entry still
     * queues an {@code ExecuteCommand} per source), so the command that
     * replaces the stage machinery must charge the per-stage debits itself.
     *
     * <p>The charge is deliberately ungated: vanilla charges a stage debit
     * even when an earlier stage produced no sources, and can drive the quota
     * negative; only the per-source {@code ExecuteCommand} dequeue is gated on
     * a positive quota.
     */
    public static void chargeInlinedModifierStages(int stages) {
        ExecutionContext<?> context = currentContext();
        if (context == null || stages <= 0) {
            return;
        }
        context.incrementCost();
        if (stages > 1) {
            chargeInlinedModifierStages(stages - 1);
        }
    }

    /**
     * Reports whether vanilla would still have run this line's inner command.
     *
     * <p>Vanilla dequeues a line's per-source {@code ExecuteCommand} only
     * while the quota is positive after the stage debits; a wrapped command
     * runs after that per-source debit has already been charged, so once its
     * stage debits are charged the inner command must run only while the
     * remaining quota has not gone negative. A negative remaining quota is the
     * compiled form of vanilla stopping the queue before this line.
     */
    public static boolean inlinedInnerRunnable() {
        ExecutionContext<?> context = currentContext();
        if (context == null) {
            return true;
        }
        @SuppressWarnings("unchecked")
        ExecutionContextAccessor<CommandSourceStack> accessor =
                (ExecutionContextAccessor<CommandSourceStack>) (Object) context;
        return accessor.functionCompiler$getCommandQuota() >= 0;
    }
}
