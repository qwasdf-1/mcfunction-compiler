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
 * IR-020, RESEARCH ONLY. Measures the exact original Blastback restore-job
 * selector fork without changing source resolution, evaluation, the command
 * callback, frame, quota, or queue.
 *
 * Distinct boundaries:
 *  - BuildContexts.execute (source/context modifier + fork generation stage);
 *  - ExecuteCommand.execute (one native command execution, including leaf);
 *  - original scoreboard terminal Command.run (nested inside execute stage).
 *
 * Samples are NOT a disjoint CPU breakdown. The first stage cannot be
 * interpreted as exclusively selector scanning without more attribution.
 * The third is nested within the second. Neither interval is necessarily
 * removable compiler work.
 *
 * No clock reads if neither FC_CPU020_NAMESPACE=erb nor mode=empty|timed.
 * All modes require explicit start/stop control and exact original command.
 */
public final class CompilerRestoreCpuProbe {
    private static final String MODE = System.getenv("FC_CPU020_MODE");
    private static final String NAMESPACE = System.getenv("FC_CPU020_NAMESPACE");
    private static final String TARGET_FUNCTION = "erb:restore/job_tick";
    private static final String ORIGINAL_COMMAND =
            "execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] "
            + "if score @s erb.job = #active erb.job "
            + "run scoreboard players set #needs_restore erb.tmp 1";

    private static final boolean CONFIGURED = "erb".equals(NAMESPACE)
            && ("plain".equals(MODE) || "empty".equals(MODE) || "timed".equals(MODE));
    private static final ThreadMXBean CLOCK = ManagementFactory.getThreadMXBean();
    private static final int BUILD = 0;
    private static final int EXECUTE = 1;
    private static final int LEAF = 2;
    private static final Stream[] STREAMS = {
            new Stream("restore_selector_build", 16),
            new Stream("restore_terminal_execute", 128),
            new Stream("restore_scoreboard_leaf", 128)
    };
    private static volatile boolean ACTIVE;

    private static final class Stream {
        final String label;
        final int stride;
        final AtomicLong visits = new AtomicLong();
        final AtomicLong samples = new AtomicLong();
        final AtomicLong cpuNs = new AtomicLong();
        final AtomicLong invalid = new AtomicLong();

        Stream(String label, int stride) {
            this.label = label;
            this.stride = stride;
        }

        void reset() {
            visits.set(0);
            samples.set(0);
            cpuNs.set(0);
            invalid.set(0);
        }

        void record(long value) {
            if (value < 0) {
                invalid.incrementAndGet();
            } else {
                samples.incrementAndGet();
                cpuNs.addAndGet(value);
            }
        }
    }

    private CompilerRestoreCpuProbe() {}

    public static boolean enabledFor(Identifier id) {
        return CONFIGURED && id != null && TARGET_FUNCTION.equals(id.toString());
    }

    private static int originalKind(String input) {
        return ORIGINAL_COMMAND.equals(input) ? BUILD : -1;
    }

    private static long clock() {
        return CLOCK.getCurrentThreadCpuTime();
    }

    private static long begin(int kind) {
        if (!ACTIVE || kind < 0) return -1L;
        Stream stream = STREAMS[kind];
        long ordinal = stream.visits.incrementAndGet();
        if ("plain".equals(MODE) || ordinal % stream.stride != 0) return -1L;
        if ("empty".equals(MODE)) {
            long begin = clock();
            stream.record(clock() - begin);
            return -1L;
        }
        return clock();
    }

    private static void end(int kind, long started) {
        if (started >= 0 && kind >= 0) {
            STREAMS[kind].record(clock() - started);
        }
    }

    public static long beginBuild(String input) {
        return begin(originalKind(input));
    }

    public static void endBuild(String input, long start) {
        end(originalKind(input), start);
    }

    public static long beginExecute(String input) {
        return begin(ORIGINAL_COMMAND.equals(input) ? EXECUTE : -1);
    }

    public static void endExecute(String input, long start) {
        end(ORIGINAL_COMMAND.equals(input) ? EXECUTE : -1, start);
    }

    /** Preserve the exact original parsed callback and CommandContext. */
    private record TimedLeaf<T extends ExecutionCommandSource<T>>(
            Command<T> original
    ) implements Command<T> {
        @Override
        public int run(CommandContext<T> context) throws CommandSyntaxException {
            long started = begin(LEAF);
            try {
                return original.run(context);
            } finally {
                end(LEAF, started);
            }
        }
    }

    private record Instrumented<T extends ExecutionCommandSource<T>>(
            InstantiatedFunction<T> delegate, List<UnboundEntryAction<T>> entries
    ) implements InstantiatedFunction<T> {
        @Override
        public Identifier id() { return delegate.id(); }
    }

    @SuppressWarnings("unchecked")
    public static <T extends ExecutionCommandSource<T>> InstantiatedFunction<T> instrument(
            InstantiatedFunction<T> original, Identifier id
    ) {
        if (!enabledFor(id) || original instanceof Instrumented<?>) return original;
        List<UnboundEntryAction<T>> entries = new ArrayList<>(original.entries());
        int found = 0;
        for (UnboundEntryAction<T> entry : entries) {
            if (!(entry instanceof BuildContexts.Unbound<?>)) continue;
            BuildContextsAccessor<T> accessor = (BuildContextsAccessor<T>) (Object) entry;
            if (!ORIGINAL_COMMAND.equals(accessor.functionCompiler$getCommandInput())) continue;
            found++;
            ContextChain<T> chain = accessor.functionCompiler$getCommand();
            while (chain != null && chain.getStage() != ContextChain.Stage.EXECUTE) {
                chain = chain.nextStage();
            }
            if (chain == null) throw new IllegalStateException("IR-020 native command has no terminal");
            CommandContext<T> terminal = chain.getTopContext();
            Command<T> callback = terminal.getCommand();
            if (callback == null || callback instanceof CustomCommandExecutor<?>) {
                throw new IllegalStateException("IR-020 publisher terminal is not an ordinary callback");
            }
            ((CommandContextAccessor<T>) (Object) terminal)
                    .functionCompiler$setCommand(new TimedLeaf<>(callback));
        }
        if (found != 1) {
            throw new IllegalStateException(
                    "IR-020 exact original Blastback restore selector source changed: " + found);
        }
        return new Instrumented<>(original, List.copyOf(entries));
    }

    public static int start(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(Component.literal(
                    "FC_CPU020 requires erb namespace and plain|empty|timed mode"));
            return 0;
        }
        if (!"plain".equals(MODE)) {
            if (!CLOCK.isCurrentThreadCpuTimeSupported()) {
                source.sendFailure(Component.literal("FC_CPU020 Server thread CPU clock unsupported"));
                return 0;
            }
            if (!CLOCK.isThreadCpuTimeEnabled()) CLOCK.setThreadCpuTimeEnabled(true);
            if (clock() < 0) {
                source.sendFailure(Component.literal("FC_CPU020 Server thread CPU clock unavailable"));
                return 0;
            }
        }
        ACTIVE = false;
        for (Stream stream : STREAMS) stream.reset();
        ACTIVE = true;
        source.sendSuccess(() -> Component.literal("FC_CPU020 started mode=" + MODE), false);
        return 1;
    }

    public static int stop(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_CPU020 was not active"));
            return 0;
        }
        ACTIVE = false; // never time log, RCON response, or event-stop command
        FunctionCompilerMod.LOGGER.info("FC_CPU020_BEGIN mode={}", MODE);
        for (Stream s : STREAMS) {
            FunctionCompilerMod.LOGGER.info(
                    "FC_CPU020_ROW kind={} stride={} visits={} samples={} cpu_ns={} invalid={}",
                    s.label, s.stride, s.visits.get(), s.samples.get(),
                    s.cpuNs.get(), s.invalid.get());
        }
        FunctionCompilerMod.LOGGER.info("FC_CPU020_END mode={}", MODE);
        source.sendSuccess(() -> Component.literal(
                "FC_CPU020 ended mode=" + MODE
                + " build=" + STREAMS[BUILD].visits.get()
                + " execute=" + STREAMS[EXECUTE].visits.get()
                + " leaf=" + STREAMS[LEAF].visits.get()), false);
        return 1;
    }
}
