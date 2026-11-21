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
import java.util.Locale;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Diagnostic-only CPU-clock screen for the pinned vm:queue/enqueue_here path.
 * No new Mixin and no compiler lowering. Nothing is timed without BOTH env
 * switches and an explicit RCON event window.
 *
 * Timed spans deliberately observe only synchronous, on-thread methods:
 * (1) the original positioned BuildContexts action, (2) immediate
 * CallFunction.execute setup, (3) ordinary Brigadier leaf callbacks inside
 * enqueue_here. Nested queued work/custom executors are NOT fully timed.
 */
public final class CompilerPositionedCpuProbe {
    private static final String NAMESPACE = System.getenv("FC_CPU004_NAMESPACE");
    private static final String MODE_NAME = System.getenv("FC_CPU004_MODE");
    private static final String FACES = "vm:queue/enqueue_faces";
    private static final String DIAGONALS = "vm:queue/enqueue_diagonals";
    private static final String CHILD = "vm:queue/enqueue_here";
    private static final int STRIDE = 16;
    private static final ThreadMXBean CLOCK = ManagementFactory.getThreadMXBean();
    private static final String MODE = MODE_NAME == null ? "" : MODE_NAME.toLowerCase(Locale.ROOT);
    private static final boolean CONFIGURED = "vm".equals(NAMESPACE)
            && ("plain".equals(MODE) || "empty".equals(MODE) || "timed".equals(MODE));
    private static final Counters POSITIONED = new Counters("positioned_entry");
    private static final Counters CALL = new Counters("enqueue_call_setup");
    private static final Counters BODY = new Counters("enqueue_body_leaf");
    private static volatile boolean ACTIVE;

    private CompilerPositionedCpuProbe() {}

    public static boolean enabledFor(Identifier id) {
        return CONFIGURED && id != null &&
                (FACES.equals(id.toString()) || DIAGONALS.equals(id.toString())
                        || CHILD.equals(id.toString()));
    }

    public static boolean isEnqueueCall(Identifier id) {
        return ACTIVE && id != null && CHILD.equals(id.toString());
    }

    private static final class Counters {
        final String kind;
        final AtomicLong calls = new AtomicLong();
        final AtomicLong samples = new AtomicLong();
        final AtomicLong cpuNs = new AtomicLong();
        final AtomicLong invalid = new AtomicLong();

        Counters(String kind) { this.kind = kind; }
        void reset() {
            calls.set(0); samples.set(0); cpuNs.set(0); invalid.set(0);
        }
        long visited() { return calls.incrementAndGet(); }
        void record(long nanos) {
            if (nanos < 0) {
                invalid.incrementAndGet();
            } else {
                samples.incrementAndGet();
                cpuNs.addAndGet(nanos);
            }
        }
    }

    private static long clock() { return CLOCK.getCurrentThreadCpuTime(); }
    private static boolean sampled(long ordinal) { return ordinal % STRIDE == 0; }

    private static <T extends ExecutionCommandSource<T>> void timedAction(
            Counters counter, UnboundEntryAction<T> original, T source,
            net.minecraft.commands.execution.ExecutionContext<T> context,
            net.minecraft.commands.execution.Frame frame
    ) {
        if (!ACTIVE) {
            original.execute(source, context, frame);
            return;
        }
        long ordinal = counter.visited();
        if ("plain".equals(MODE) || !sampled(ordinal)) {
            original.execute(source, context, frame);
            return;
        }
        if ("empty".equals(MODE)) {
            long a = clock();
            counter.record(clock() - a);
            original.execute(source, context, frame);
            return;
        }
        long a = clock();
        try {
            original.execute(source, context, frame);
        } finally {
            counter.record(clock() - a);
        }
    }

    private static <T extends ExecutionCommandSource<T>> int timedCallback(
            Counters counter, Command<T> original, CommandContext<T> context
    ) throws CommandSyntaxException {
        if (!ACTIVE) return original.run(context);
        long ordinal = counter.visited();
        if ("plain".equals(MODE) || !sampled(ordinal)) return original.run(context);
        if ("empty".equals(MODE)) {
            long a = clock();
            counter.record(clock() - a);
            return original.run(context);
        }
        long a = clock();
        try {
            return original.run(context);
        } finally {
            counter.record(clock() - a);
        }
    }

    /** Called only on the CallFunction.execute boundary, not child body. */
    public static long callHead(Identifier id) {
        if (!isEnqueueCall(id)) return -1L;
        long ordinal = CALL.visited();
        if ("plain".equals(MODE) || !sampled(ordinal)) return -1L;
        if ("empty".equals(MODE)) {
            long a = clock();
            CALL.record(clock() - a);
            return -1L;
        }
        return clock();
    }

    public static void callTail(long started) {
        if (started >= 0) CALL.record(clock() - started);
    }

    @SuppressWarnings("unchecked")
    public static <T extends ExecutionCommandSource<T>> InstantiatedFunction<T> instrument(
            InstantiatedFunction<T> original, Identifier id
    ) {
        if (!enabledFor(id) || original instanceof InstrumentedInstantiation<?>) {
            return original;
        }
        boolean child = CHILD.equals(id.toString());
        List<UnboundEntryAction<T>> entries = new ArrayList<>(original.entries().size());
        for (UnboundEntryAction<T> entry : original.entries()) {
            if (!(entry instanceof BuildContexts.Unbound<?> buildContexts)) {
                entries.add(entry);
                continue;
            }
            BuildContextsAccessor<T> accessor = (BuildContextsAccessor<T>) (Object) buildContexts;
            String input = accessor.functionCompiler$getCommandInput();
            if (!child) {
                if (input != null && input.startsWith("execute positioned ")
                        && input.contains("run function vm:queue/enqueue_here")) {
                    entries.add((source, context, frame) ->
                            timedAction(POSITIONED, entry, source, context, frame));
                } else {
                    entries.add(entry);
                }
                continue;
            }
            ContextChain<T> chain = accessor.functionCompiler$getCommand();
            while (chain != null && chain.getStage() != ContextChain.Stage.EXECUTE) {
                chain = chain.nextStage();
            }
            if (chain != null) {
                CommandContext<T> terminal = chain.getTopContext();
                Command<T> originalCommand = terminal.getCommand();
                if (originalCommand != null
                        && !(originalCommand instanceof CustomCommandExecutor<?>)
                        && !(originalCommand instanceof TimedBodyCommand<?>)) {
                    ((CommandContextAccessor<T>) (Object) terminal)
                            .functionCompiler$setCommand(
                                new TimedBodyCommand<>(originalCommand));
                }
            }
            entries.add(entry);
        }
        return new InstrumentedInstantiation<>(original, List.copyOf(entries));
    }

    private record TimedBodyCommand<T extends ExecutionCommandSource<T>>(
            Command<T> delegate
    ) implements Command<T> {
        @Override
        public int run(CommandContext<T> context) throws CommandSyntaxException {
            return timedCallback(BODY, delegate, context);
        }
    }

    private record InstrumentedInstantiation<T extends ExecutionCommandSource<T>>(
            InstantiatedFunction<T> original,
            List<UnboundEntryAction<T>> entries
    ) implements InstantiatedFunction<T> {
        @Override
        public Identifier id() { return original.id(); }
    }

    public static int start(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(Component.literal("FC_CPU004 disabled: set mode and vm namespace"));
            return 0;
        }
        if (!"plain".equals(MODE)) {
            if (!CLOCK.isCurrentThreadCpuTimeSupported()) {
                source.sendFailure(Component.literal("FC_CPU004 current-thread CPU clock unsupported"));
                return 0;
            }
            if (!CLOCK.isThreadCpuTimeEnabled()) CLOCK.setThreadCpuTimeEnabled(true);
            if (clock() < 0) {
                source.sendFailure(Component.literal("FC_CPU004 current-thread CPU clock unavailable"));
                return 0;
            }
        }
        ACTIVE = false;
        POSITIONED.reset(); CALL.reset(); BODY.reset();
        ACTIVE = true;
        source.sendSuccess(() -> Component.literal("FC_CPU004 started mode=" + MODE), false);
        return 1;
    }

    public static int stop(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_CPU004 was not active"));
            return 0;
        }
        ACTIVE = false;
        FunctionCompilerMod.LOGGER.info("FC_CPU004_BEGIN mode={} stride={}", MODE, STRIDE);
        for (Counters c : new Counters[]{POSITIONED, CALL, BODY}) {
            FunctionCompilerMod.LOGGER.info(
                    "FC_CPU004_ROW kind={} calls={} samples={} cpu_ns={} invalid={}",
                    c.kind, c.calls.get(), c.samples.get(), c.cpuNs.get(), c.invalid.get());
        }
        FunctionCompilerMod.LOGGER.info("FC_CPU004_END mode={} stride={}", MODE, STRIDE);
        source.sendSuccess(() -> Component.literal("FC_CPU004 ended mode=" + MODE
                + " positioned=" + POSITIONED.calls.get()
                + " call_setup=" + CALL.calls.get()
                + " body_leaf=" + BODY.calls.get()), false);
        return 1;
    }
}
