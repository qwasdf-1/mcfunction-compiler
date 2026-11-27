package dev.functioncompiler;

import dev.functioncompiler.mixin.ExecutionContextAccessor;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.CommandQueueEntry;
import net.minecraft.commands.execution.EntryAction;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.functions.InstantiatedFunction;

import java.util.List;
import java.util.concurrent.atomic.LongAdder;

/**
 * COMPILER-IR-012: opt-in function-level scheduling using the exact same
 * generated typed-IR bytecode as the ordinary CallFunction/ContinuationTask
 * path. A cursor materializes one compiled chunk at a time and queues its
 * successor *after* the current chunk returns, retaining depth-first staging
 * against the caller's pending siblings and the vanilla command quota.
 *
 * A direct call is only legal with no function/parent/source result callbacks,
 * no return-parent mode, no tracer and a wholly typed source function. Every
 * other call site takes the untouched vanilla CallFunction path. Unsupported
 * commands, macro functions, forks, returns and inner calls NEVER qualify.
 *
 * Important remaining compatibility limitation: arbitrary mods can enqueue
 * work synchronously from a scoreboard listener *inside* a compiled chunk.
 * The IR-008 region execution boundary already batches those commands and
 * may reorder such injected work relative to individual vanilla commands.
 * This scheduler therefore stays research-only, not a universal replacement.
 */
public final class TypedScoreIRDirectScheduler {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIRECT_FUNCTION"));
    private static final boolean TOGGLE_ALLOWED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIRECT_FUNCTION_TOGGLE"));
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));

    private static volatile boolean active = ENABLED;
    private static final LongAdder ELIGIBLE = new LongAdder();
    private static final LongAdder EXECUTED = new LongAdder();
    private static final LongAdder FALLBACK = new LongAdder();
    private static final LongAdder CHUNKS = new LongAdder();
    private static final LongAdder RESUMES = new LongAdder();

    private TypedScoreIRDirectScheduler() {}

    static boolean compilationEnabled() { return ENABLED; }

    static void eligibleCompiled() {
        if (DIAGNOSTICS) ELIGIBLE.increment();
    }

    static int toggle(CommandSourceStack source, boolean enabled) {
        if (!ENABLED || !TOGGLE_ALLOWED) return 0;
        active = enabled;
        source.sendSuccess(() -> net.minecraft.network.chat.Component.literal(
                "IR012 direct function enabled=" + enabled), false);
        return 1;
    }

    static String diagnostics() {
        return " direct_function=" + active
                + " direct_function_eligible=" + ELIGIBLE.sum()
                + " direct_function_executed=" + EXECUTED.sum()
                + " direct_function_fallback=" + FALLBACK.sum()
                + " direct_function_chunks=" + CHUNKS.sum()
                + " direct_function_resumes=" + RESUMES.sum();
    }

    /**
     * Intercepts the CallFunction queue entry, not /function parsing.
     * The vanilla call entry is already dequeued by ExecutionContext, so
     * charge precisely CallFunction's one function-call debit and stage only
     * one resumable compiled chunk. No child frame is needed under these
     * strict callback/return/tracing guards.
     */
    public static <T extends ExecutionCommandSource<T>> boolean tryExecute(
            InstantiatedFunction<T> function,
            T sender,
            ExecutionContext<T> context,
            Frame callerFrame,
            CommandResultCallback functionCallback,
            boolean returnParentFrame
    ) {
        if (!ENABLED || !active) return false;
        List<UnboundEntryAction<CommandSourceStack>> chunks =
                TypedScoreIR.directFunctionChunks(function);
        if (chunks == null) return false;
        if (returnParentFrame
                || functionCallback != CommandResultCallback.EMPTY
                || context.tracer() != null
                || sender.callback() != CommandResultCallback.EMPTY
                || !(sender instanceof CommandSourceStack source)) {
            if (DIAGNOSTICS) FALLBACK.increment();
            return false;
        }

        @SuppressWarnings("unchecked")
        ExecutionContext<CommandSourceStack> engine =
                (ExecutionContext<CommandSourceStack>) (Object) context;
        var quota = (ExecutionContextAccessor<CommandSourceStack>) (Object) engine;
        if (quota.functionCompiler$getCommandQuota() <= 0) return false;
        engine.incrementCost(); // vanilla CallFunction's one debit
        if (DIAGNOSTICS) EXECUTED.increment();

        engine.queueNext(new CommandQueueEntry<>(callerFrame,
                new Resume(source, chunks, 0)));
        return true;
    }

    /**
     * The queued action's immutable PC avoids eagerly staging all function
     * commands. Each native queued step is a *compiled IR chunk*, not one
     * Brigadier BuildContexts/ExecuteCommand action per original command.
     */
    private record Resume(
            CommandSourceStack source,
            List<UnboundEntryAction<CommandSourceStack>> chunks,
            int pc
    ) implements EntryAction<CommandSourceStack> {
        @Override
        public void execute(ExecutionContext<CommandSourceStack> context, Frame frame) {
            var quota = (ExecutionContextAccessor<CommandSourceStack>) (Object) context;
            if (quota.functionCompiler$getCommandQuota() <= 0) return;
            if (DIAGNOSTICS) {
                CHUNKS.increment();
                if (pc > 0) RESUMES.increment();
            }
            chunks.get(pc).execute(source, context, frame);
            // The compiled step has already consumed exact per-command and
            // modifier-stage costs. Never queue later chunks once exhausted.
            if (pc + 1 < chunks.size() && quota.functionCompiler$getCommandQuota() > 0) {
                context.queueNext(new CommandQueueEntry<>(frame,
                        new Resume(source, chunks, pc + 1)));
            }
        }
    }
}
