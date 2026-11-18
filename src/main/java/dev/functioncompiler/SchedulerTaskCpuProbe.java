package dev.functioncompiler;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.Locale;

/**
 * SCHED-ATTR-025: calibrated, deterministic sparse CPU clock measurements
 * of four vanilla execution task methods. Enabled ONLY with the event-bounded
 * SchedulerPathCensus. The same ~1/32 ordinal selection is applied in EMPTY
 * and TIMED independent boots. No CPU clocks are read on unsampled calls.
 *
 * These are inclusive method intervals and may overlap; never sum their
 * projected CPU costs as though they were disjoint or recoverable overhead.
 */
public final class SchedulerTaskCpuProbe {
    public enum Path { BUILD, EXECUTE, CALL, CONTINUATION }
    public enum Mode { OFF, EMPTY, TIMED }

    public static final int SAMPLE_DENOMINATOR = 32;
    private static final Mode MODE = parseMode(System.getenv("FC_SCHED_TASK_CPU_PROBE"));
    private static final ThreadMXBean CLOCK =
            MODE == Mode.OFF ? null : ManagementFactory.getThreadMXBean();
    private static final long[] SALTS = {
            0x159a3c123a43cf1bL, 0x6db5a4f21207e391L,
            0x35f177b00832481dL, 0x1f14cacde72f61bdL,
    };
    private static final Stats[] STATS = new Stats[Path.values().length];
    private static long ownerThreadId = -1L;

    static {
        for (int i = 0; i < STATS.length; i++) {
            STATS[i] = new Stats();
        }
    }

    private static final class Stats {
        long calls;
        long samples;
        long cpuNanos;
        long zeroDeltas;
        long nested;
        int depth;
        boolean sampled;
        long begun;
    }

    private SchedulerTaskCpuProbe() {}

    private static Mode parseMode(String raw) {
        if (raw == null || raw.isBlank() || raw.equalsIgnoreCase("off")) {
            return Mode.OFF;
        }
        return switch (raw.toLowerCase(Locale.ROOT)) {
            case "empty" -> Mode.EMPTY;
            case "timed" -> Mode.TIMED;
            default -> throw new IllegalArgumentException(
                    "FC_SCHED_TASK_CPU_PROBE must be off, empty, or timed");
        };
    }

    public static String modeName() { return MODE.name().toLowerCase(Locale.ROOT); }
    public static boolean enabled() { return MODE != Mode.OFF; }

    public static boolean clockReady() {
        return enabled() && CLOCK.isCurrentThreadCpuTimeSupported()
                && CLOCK.isThreadCpuTimeEnabled();
    }

    public static void ensureReady() {
        if (!enabled()) return;
        if (!SchedulerPathCensus.enabled()) {
            throw new IllegalStateException("Sparse task CPU probe requires event-scoped path census");
        }
        if (!clockReady() || CLOCK.getCurrentThreadCpuTime() < 0L) {
            throw new IllegalStateException("Java current-thread CPU clock unsupported or disabled");
        }
        for (String flag : new String[]{
                "FC_SCORE_ADD_TIMING", "FC_SCORE_ADD_METRICS",
                "FC_SCORE_ADD_PHASE_TIMERS", "FC_SCHED_ARCH_COUNTERS",
                "FC_COMMAND_CALLBACK_METRICS", "FC_RUNTIME_TRACE",
                "FC_SCHED_QUEUE_CPU_PROBE", "FC_SCORE_ADD_CPU_PROBE"}) {
            String value = System.getenv(flag);
            if (value != null && !value.isBlank()
                    && !value.equalsIgnoreCase("false")
                    && !value.equalsIgnoreCase("off")) {
                throw new IllegalStateException("Incompatible callback metric: " + flag);
            }
        }
    }

    private static long cpuNanos() {
        long cpu = CLOCK.getCurrentThreadCpuTime();
        if (cpu < 0) throw new IllegalStateException("Current thread CPU clock returned -1");
        return cpu;
    }

    private static long mix64(long input) {
        // Stable ordinal hash, different salt per task type; avoids aligning
        // a modulo-32 sample with datapack's naturally periodic function loop.
        long x = input;
        x = (x ^ (x >>> 33)) * 0xff51afd7ed558ccdL;
        x = (x ^ (x >>> 33)) * 0xc4ceb9fe1a85ec53L;
        return x ^ (x >>> 33);
    }

    public static void enter(Path path) {
        if (MODE == Mode.OFF || !SchedulerPathCensus.recording()) return;
        Stats stat = STATS[path.ordinal()];
        stat.calls++;
        if (stat.depth != 0) {
            stat.nested++;
            stat.depth++;
            return;
        }
        stat.depth = 1;
        stat.sampled = (mix64(stat.calls ^ SALTS[path.ordinal()])
                & (SAMPLE_DENOMINATOR - 1)) == 0;
        if (!stat.sampled) return;

        long threadId = Thread.currentThread().threadId();
        if (ownerThreadId == -1L) {
            ownerThreadId = threadId;
        } else if (ownerThreadId != threadId) {
            throw new IllegalStateException("Sparse task probe changed Java thread");
        }

        if (MODE == Mode.EMPTY) {
            long started = cpuNanos();
            long elapsed = cpuNanos() - started;
            record(stat, elapsed);
        } else {
            stat.begun = cpuNanos();
        }
    }

    public static void exit(Path path) {
        if (MODE == Mode.OFF) return;
        Stats stat = STATS[path.ordinal()];
        if (stat.depth == 0) return;
        stat.depth--;
        if (stat.depth != 0) return;
        if (stat.sampled && MODE == Mode.TIMED) {
            record(stat, cpuNanos() - stat.begun);
        }
        stat.sampled = false;
    }

    private static void record(Stats stat, long elapsed) {
        if (elapsed < 0) throw new IllegalStateException("CPU clock regressed");
        stat.samples = Math.addExact(stat.samples, 1L);
        stat.cpuNanos = Math.addExact(stat.cpuNanos, elapsed);
        if (elapsed == 0) stat.zeroDeltas++;
    }

    private static Stats get(Path path) { return STATS[path.ordinal()]; }
    /** True only inside a selected parent task method's real execution body.
     * This exposes the exact previously frozen 1/32 ordinal selection to
     * nested SCHED-ATTR-026 probes without creating another random stream.
     */
    public static boolean activeSampled(Path p) {
        if (MODE == Mode.OFF) return false;
        Stats stat = get(p);
        return stat.depth > 0 && stat.sampled;
    }

    public static long ownerThreadId() { return ownerThreadId; }
    public static long calls(Path p) { return get(p).calls; }
    public static long samples(Path p) { return get(p).samples; }
    public static long cpuNanos(Path p) { return get(p).cpuNanos; }
    public static long zeroDeltas(Path p) { return get(p).zeroDeltas; }
    public static long nested(Path p) { return get(p).nested; }
    public static int depth(Path p) { return get(p).depth; }
}
