package dev.functioncompiler;

import dev.functioncompiler.mixin.ExecutionContextAccessor;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Experimental alternative scheduling path for a strictly whitelisted,
 * straight-line, literal fake-holder ScoreAdd function.
 *
 * <p>C (fused) still enqueues a CallFunction child frame and a ContinuationTask
 * before its single fused queue entry. D uses the existing CallFunction entry
 * as the only scheduling boundary and advances a local program counter,
 * preserving the call debit and every vanilla command debit. Unsupported
 * contexts fall back to C's original fused function unchanged. No arbitrary
 * Minecraft command, fork, return, macro or recursion enters this path.
 *
 * <p>Not a general ExecutionContext replacement; the dispatcher for all
 * unrelated queue actions remains vanilla.
 */
public final class DirectSchedulerPrototype {
    // Narrow by design. Generalizing requires separate proofs and tests.
    private static final String SAFE_LITERAL_COMMAND =
            "scoreboard players add #x fc_sched 1";
    private static final ConcurrentMap<Identifier, AtomicLong> COMPILED =
            new ConcurrentHashMap<>();
    private static final ConcurrentMap<Identifier, AtomicLong> EXECUTED =
            new ConcurrentHashMap<>();
    private static final ConcurrentMap<Identifier, AtomicLong> FALLBACKS =
            new ConcurrentHashMap<>();

    private DirectSchedulerPrototype() {
    }

    public static InstantiatedFunction<CommandSourceStack> compile(
            PlainTextFunction<CommandSourceStack> original
    ) {
        // This also creates and retains the proven C fallback representation.
        InstantiatedFunction<CommandSourceStack> fusedFallback =
                FusedRegionPrototype.compile(original);
        if (original.id() == null || original.entries().size() < 2
                || !original.id().getPath().matches("score_[0-9]+")) {
            return fusedFallback;
        }
        List<FusedRegionPrototype.FusedCommand> safeCommands = new ArrayList<>();
        for (var entry : original.entries()) {
            var candidate = FusedRegionPrototype.fusedCommand(entry);
            if (candidate == null
                    || !SAFE_LITERAL_COMMAND.equals(candidate.commandInput())
                    || !(candidate.command().getTopContext().getCommand()
                    instanceof ScoreAddCommand)) {
                return fusedFallback;
            }
            safeCommands.add(candidate);
        }
        // No direct execution if fusion itself fell back on compilation.
        if (fusedFallback == original || fusedFallback.entries().size() != 1) {
            return fusedFallback;
        }
        COMPILED.computeIfAbsent(original.id(), ignored -> new AtomicLong())
                .incrementAndGet();
        return new DirectFunction(original, fusedFallback, List.copyOf(safeCommands));
    }

    /** True only if this function can be safely bypassed in this call context. */
    public static <T extends ExecutionCommandSource<T>> boolean tryExecute(
            InstantiatedFunction<T> function,
            T sender,
            ExecutionContext<T> context,
            Frame callerFrame,
            CommandResultCallback functionCallback,
            boolean returnParentFrame
    ) {
        if (!(function instanceof DirectFunction direct)) {
            return false;
        }
        // Vanilla creates a child frame to hold callbacks, return propagation,
        // and traced call boundaries. We cannot skip that frame in such modes.
        if (returnParentFrame || functionCallback != CommandResultCallback.EMPTY
                || context.tracer() != null
                || !(sender instanceof CommandSourceStack source)) {
            if (ProbeConfiguration.directSchedulerDiagnosticsEnabled()) {
                FALLBACKS.computeIfAbsent(direct.id(), ignored -> new AtomicLong())
                        .incrementAndGet();
            }
            return false;
        }

        @SuppressWarnings("unchecked")
        ExecutionContext<CommandSourceStack> typedContext =
                (ExecutionContext<CommandSourceStack>) (Object) context;
        ExecutionContextAccessor<CommandSourceStack> accessor =
                (ExecutionContextAccessor<CommandSourceStack>) (Object) typedContext;
        if (accessor.functionCompiler$getCommandQuota() <= 0) {
            return false;
        }

        // Match CallFunction's one function-call quota cost. The caller's
        // pending siblings remain on vanilla's queue and are processed later.
        typedContext.incrementCost();
        if (ProbeConfiguration.directSchedulerDiagnosticsEnabled()) {
            EXECUTED.computeIfAbsent(direct.id(), ignored -> new AtomicLong())
                    .incrementAndGet();
        }
        // A local program counter runs ONLY known non-scheduling commands.
        // FusedRegionPrototype.executeCommand retains per-command quota,
        // CommandSyntaxException, source callback and result semantics.
        for (int pc = 0; pc < direct.commands.size(); pc++) {
            if (!FusedRegionPrototype.executeCommand(
                    direct.commands.get(pc), source, typedContext, callerFrame)) {
                break;
            }
        }
        return true;
    }

    public static boolean retainsOriginal(
            InstantiatedFunction<?> compiled, InstantiatedFunction<?> original
    ) {
        return compiled instanceof DirectFunction direct && direct.original == original;
    }

    public static int traceEntryCount(
            InstantiatedFunction<?> compiled, int observed
    ) {
        return compiled instanceof DirectFunction direct
                ? direct.original.entries().size() : observed;
    }

    public static long compiled(Identifier id) {
        var number = COMPILED.get(id);
        return number == null ? 0 : number.get();
    }

    public static long executed(Identifier id) {
        var number = EXECUTED.get(id);
        return number == null ? 0 : number.get();
    }

    public static long fallbackInvocations(Identifier id) {
        var number = FALLBACKS.get(id);
        return number == null ? 0 : number.get();
    }

    /** Retain the exact C function for unsupported calls and reload fallback. */
    static final class DirectFunction
            implements InstantiatedFunction<CommandSourceStack> {
        private final PlainTextFunction<CommandSourceStack> original;
        private final InstantiatedFunction<CommandSourceStack> fusedFallback;
        private final List<FusedRegionPrototype.FusedCommand> commands;

        private DirectFunction(
                PlainTextFunction<CommandSourceStack> original,
                InstantiatedFunction<CommandSourceStack> fusedFallback,
                List<FusedRegionPrototype.FusedCommand> commands
        ) {
            this.original = original;
            this.fusedFallback = fusedFallback;
            this.commands = commands;
        }

        @Override
        public Identifier id() {
            return original.id();
        }

        @Override
        public List<net.minecraft.commands.execution.UnboundEntryAction<CommandSourceStack>> entries() {
            return fusedFallback.entries();
        }
    }
}
