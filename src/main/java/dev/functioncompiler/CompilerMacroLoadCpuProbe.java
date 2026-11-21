package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * COMPILER-MACRO-006, research only.
 *
 * Measures the existing macro-instantiation path for the single SHA-pinned
 * vm:queue/load_next function. No new Mixins, command replacements, or
 * production optimizers. Counters only run inside an explicit RCON event
 * window; the three modes use separate fresh Minecraft JVMs.
 *
 * The total span includes both nested component spans. Never add the
 * components or treat total/vanilla instantiate as entirely avoidable.
 */
public final class CompilerMacroLoadCpuProbe {
    private static final String MODE = System.getenv("FC_MACRO006_MODE");
    private static final String NAMESPACE = System.getenv("FC_MACRO006_NAMESPACE");
    private static final boolean CONFIGURED =
            "vm".equals(NAMESPACE)
                    && ("plain".equals(MODE) || "empty".equals(MODE) || "timed".equals(MODE));
    private static final int STRIDE = 8;
    public static final int TOTAL = 0;
    public static final int EXTRACTION = 1;
    public static final int VANILLA_INSTANTIATION = 2;
    private static final ThreadMXBean CLOCK = ManagementFactory.getThreadMXBean();
    private static final String TARGET = "vm:queue/load_next";
    private static final Stream[] STREAMS = {
            new Stream("macro_total"),
            new Stream("argument_extraction"),
            new Stream("vanilla_macro_instantiation"),
    };
    private static final AtomicLong CACHE_HITS = new AtomicLong();
    private static final AtomicLong EXTRACT_NULL = new AtomicLong();
    private static volatile boolean ACTIVE;

    private static final class Stream {
        private final String kind;
        private final AtomicLong calls = new AtomicLong();
        private final AtomicLong samples = new AtomicLong();
        private final AtomicLong cpuNs = new AtomicLong();
        private final AtomicLong invalid = new AtomicLong();

        private Stream(String kind) { this.kind = kind; }
        private void reset() {
            calls.set(0);
            samples.set(0);
            cpuNs.set(0);
            invalid.set(0);
        }
        private void sample(long delta) {
            if (delta < 0) {
                invalid.incrementAndGet();
            } else {
                samples.incrementAndGet();
                cpuNs.addAndGet(delta);
            }
        }
    }

    private CompilerMacroLoadCpuProbe() {}

    public static boolean enabledFor(Identifier id) {
        return CONFIGURED && id != null && TARGET.equals(id.toString());
    }

    private static long now() { return CLOCK.getCurrentThreadCpuTime(); }

    public static long begin(Identifier id, int kind) {
        if (!ACTIVE || !enabledFor(id)) return -1L;
        Stream stream = STREAMS[kind];
        long call = stream.calls.incrementAndGet();
        if ("plain".equals(MODE) || call % STRIDE != 0) return -1L;
        if ("empty".equals(MODE)) {
            long start = now();
            stream.sample(now() - start);
            return -1L;
        }
        return now();
    }

    public static void finish(int kind, long start) {
        if (start >= 0) STREAMS[kind].sample(now() - start);
    }

    public static void cacheHit(Identifier id) {
        if (ACTIVE && enabledFor(id)) CACHE_HITS.incrementAndGet();
    }

    public static void missingExtraction(Identifier id) {
        if (ACTIVE && enabledFor(id)) EXTRACT_NULL.incrementAndGet();
    }

    public static int start(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(Component.literal("FC_MACRO006 requires vm namespace and plain/empty/timed mode"));
            return 0;
        }
        if (!"plain".equals(MODE)) {
            if (!CLOCK.isCurrentThreadCpuTimeSupported()) {
                source.sendFailure(Component.literal("FC_MACRO006 current-thread CPU clock unsupported"));
                return 0;
            }
            if (!CLOCK.isThreadCpuTimeEnabled()) CLOCK.setThreadCpuTimeEnabled(true);
            if (now() < 0) {
                source.sendFailure(Component.literal("FC_MACRO006 current-thread CPU clock unavailable"));
                return 0;
            }
        }
        ACTIVE = false;
        for (Stream stream : STREAMS) stream.reset();
        CACHE_HITS.set(0);
        EXTRACT_NULL.set(0);
        ACTIVE = true;
        source.sendSuccess(() -> Component.literal("FC_MACRO006 started mode=" + MODE), false);
        return 1;
    }

    public static int stop(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_MACRO006 not active"));
            return 0;
        }
        ACTIVE = false;
        FunctionCompilerMod.LOGGER.info("FC_MACRO006_BEGIN mode={} stride={} function={}", MODE, STRIDE, TARGET);
        for (Stream stream : STREAMS) {
            FunctionCompilerMod.LOGGER.info(
                    "FC_MACRO006_ROW kind={} calls={} samples={} cpu_ns={} invalid={}",
                    stream.kind, stream.calls.get(), stream.samples.get(),
                    stream.cpuNs.get(), stream.invalid.get());
        }
        FunctionCompilerMod.LOGGER.info(
                "FC_MACRO006_COUNTS cache_hits={} extraction_null={}",
                CACHE_HITS.get(), EXTRACT_NULL.get());
        FunctionCompilerMod.LOGGER.info("FC_MACRO006_END mode={} stride={}", MODE, STRIDE);
        source.sendSuccess(() -> Component.literal(
                "FC_MACRO006 ended mode=" + MODE
                        + " calls=" + STREAMS[TOTAL].calls.get()
                        + " parse=" + STREAMS[VANILLA_INSTANTIATION].calls.get()
                        + " hits=" + CACHE_HITS.get()), false);
        return 1;
    }
}
