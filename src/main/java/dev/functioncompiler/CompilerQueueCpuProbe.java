package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.CommandContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

/**
 * RESEARCH-ONLY. On-thread CPU clock boundaries for the SHA-pinned Vein Miner
 * queue macro predicate, and exact append_here command shapes.
 *
 * Two opt-in @Inject-only Mixins intercept BuildContexts.execute and
 * ExecuteCommand.execute. They do not change the vanilla command context,
 * source, callback, result, or task scheduling. Default runs remain gated off.
 * Do NOT merge research Mixins into production without separately proving
 * disabled-hook overhead.
 */
public final class CompilerQueueCpuProbe {
    private static final String MODE = System.getenv("FC_CPU005_MODE");
    private static final String NAMESPACE = System.getenv("FC_CPU005_NAMESPACE");
    private static final int STRIDE = 16;
    private static final boolean CONFIGURED =
            "vm".equals(NAMESPACE)
            && ("plain".equals(MODE) || "empty".equals(MODE) || "timed".equals(MODE));
    private static final ThreadMXBean CLOCK = ManagementFactory.getThreadMXBean();

    private static final int PREDICATE = 0;
    private static final int APPEND_TP = 1;
    private static final int APPEND_FRONTIER = 2;
    private static final int APPEND_STORE = 3;
    private static final int STORE_LEAF = 4;

    private static final Stream[] STREAMS = {
            new Stream("enqueue_macro_predicate_build"),
            new Stream("append_tp_execute"),
            new Stream("append_frontier_execute"),
            new Stream("append_coordinate_store_execute"),
            new Stream("append_data_get_leaf"),
    };
    private static volatile boolean ACTIVE;

    private static final class Stream {
        final String label;
        final AtomicLong calls = new AtomicLong();
        final AtomicLong samples = new AtomicLong();
        final AtomicLong cpuNs = new AtomicLong();
        final AtomicLong invalid = new AtomicLong();

        Stream(String label) { this.label = label; }
        void reset() {
            calls.set(0); samples.set(0); cpuNs.set(0); invalid.set(0);
        }
        void observe(long nanos) {
            if (nanos < 0) invalid.incrementAndGet();
            else {
                samples.incrementAndGet();
                cpuNs.addAndGet(nanos);
            }
        }
    }

    private CompilerQueueCpuProbe() {}

    public static boolean enabledFor(Identifier id) {
        return CONFIGURED && id != null
                && ("vm:queue/append_here".equals(id.toString())
                    || "vm:queue/enqueue_match".equals(id.toString()));
    }

    private static int buildKind(String input) {
        if (input != null
                && input.startsWith("execute unless block ~ ~ ~ #vm:excluded_blocks if block ~ ~ ~ #")
                && input.endsWith(" run function vm:queue/append_here")) {
            return PREDICATE;
        }
        return -1;
    }

    private static int executeKind(String input) {
        if (input == null) return -1;
        if ("tp @s ~ ~ ~".equals(input)) return APPEND_TP;
        if ("data modify entity @s data.frontier append value {x:0,y:0,z:0}".equals(input))
            return APPEND_FRONTIER;
        if (input.startsWith("execute store result entity @s data.frontier[-1].")
                && input.contains(" run data get entity @s Pos["))
            return APPEND_STORE;
        return -1;
    }

    private static long now() { return CLOCK.getCurrentThreadCpuTime(); }

    /** -1 means no CPU interval opened. Counts every selected command call. */
    private static long begin(int kind) {
        if (kind < 0 || !ACTIVE) return -1L;
        Stream stream = STREAMS[kind];
        long ordinal = stream.calls.incrementAndGet();
        if ("plain".equals(MODE) || ordinal % STRIDE != 0) return -1L;
        if ("empty".equals(MODE)) {
            long before = now();
            stream.observe(now() - before);
            return -1L;
        }
        return now();
    }

    private static void end(int kind, long started) {
        if (kind >= 0 && started >= 0) {
            STREAMS[kind].observe(now() - started);
        }
    }

    public static long beginBuild(String input) { return begin(buildKind(input)); }
    public static void endBuild(String input, long started) {
        end(buildKind(input), started);
    }

    public static long beginExecute(String input) { return begin(executeKind(input)); }
    public static void endExecute(String input, long started) {
        end(executeKind(input), started);
    }

    /**
     * Preserve untouched ordinary Brigadier callback results and exceptions.
     * This intentionally measures data-get leaf work excluding the store-result
     * consumer; the enclosing ExecuteCommand stream includes that consumer.
     */
    private static final class LeafCommand<T extends ExecutionCommandSource<T>>
            implements Command<T> {
        private final Command<T> original;

        LeafCommand(Command<T> original) { this.original = original; }

        @Override
        public int run(CommandContext<T> context) throws CommandSyntaxException {
            long started = begin(STORE_LEAF);
            try {
                return original.run(context);
            } finally {
                end(STORE_LEAF, started);
            }
        }
    }

    private record WrappedFunction<T extends ExecutionCommandSource<T>>(
            InstantiatedFunction<T> original,
            List<UnboundEntryAction<T>> entries
    ) implements InstantiatedFunction<T> {
        @Override
        public Identifier id() { return original.id(); }
    }

    @SuppressWarnings("unchecked")
    public static <T extends ExecutionCommandSource<T>> InstantiatedFunction<T> instrument(
            InstantiatedFunction<T> original, Identifier id
    ) {
        if (!enabledFor(id) || !"vm:queue/append_here".equals(id.toString())
                || original instanceof WrappedFunction<?>) return original;
        List<UnboundEntryAction<T>> entries = new ArrayList<>(original.entries());
        for (UnboundEntryAction<T> entry : entries) {
            if (!(entry instanceof BuildContexts.Unbound<?> contexts)) continue;
            BuildContextsAccessor<T> accessor = (BuildContextsAccessor<T>) (Object) contexts;
            String input = accessor.functionCompiler$getCommandInput();
            if (executeKind(input) != APPEND_STORE) continue;
            ContextChain<T> chain = accessor.functionCompiler$getCommand();
            while (chain != null && chain.getStage() != ContextChain.Stage.EXECUTE) {
                chain = chain.nextStage();
            }
            if (chain == null) continue;
            CommandContext<T> terminal = chain.getTopContext();
            Command<T> command = terminal.getCommand();
            if (command != null && !(command instanceof CustomCommandExecutor<?>)
                    && !(command instanceof LeafCommand<?>)) {
                ((CommandContextAccessor<T>) (Object) terminal)
                        .functionCompiler$setCommand(new LeafCommand<>(command));
            }
        }
        return new WrappedFunction<>(original, List.copyOf(entries));
    }

    public static int start(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(Component.literal("FC_CPU005 requires mode and exact vm namespace"));
            return 0;
        }
        if (!"plain".equals(MODE)) {
            if (!CLOCK.isCurrentThreadCpuTimeSupported()) {
                source.sendFailure(Component.literal("FC_CPU005 Server thread CPU clock unsupported"));
                return 0;
            }
            if (!CLOCK.isThreadCpuTimeEnabled()) CLOCK.setThreadCpuTimeEnabled(true);
            if (now() < 0) {
                source.sendFailure(Component.literal("FC_CPU005 Server thread CPU clock unavailable"));
                return 0;
            }
        }
        ACTIVE = false;
        for (Stream stream : STREAMS) stream.reset();
        ACTIVE = true;
        source.sendSuccess(() -> Component.literal("FC_CPU005 started mode=" + MODE), false);
        return 1;
    }

    public static int stop(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_CPU005 was not active"));
            return 0;
        }
        ACTIVE = false;
        FunctionCompilerMod.LOGGER.info("FC_CPU005_BEGIN mode={} stride={}", MODE, STRIDE);
        for (Stream stream : STREAMS) {
            FunctionCompilerMod.LOGGER.info(
                    "FC_CPU005_ROW kind={} calls={} samples={} cpu_ns={} invalid={}",
                    stream.label, stream.calls.get(), stream.samples.get(),
                    stream.cpuNs.get(), stream.invalid.get());
        }
        FunctionCompilerMod.LOGGER.info("FC_CPU005_END mode={} stride={}", MODE, STRIDE);
        source.sendSuccess(() -> Component.literal(
                "FC_CPU005 ended mode=" + MODE
                        + " predicate=" + STREAMS[PREDICATE].calls.get()
                        + " append_stores=" + STREAMS[APPEND_STORE].calls.get()), false);
        return 1;
    }
}
