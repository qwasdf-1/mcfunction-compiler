package dev.functioncompiler;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.Locale;

/**
 * SCHED-ATTR-026: nested execution-task callsite timing, research-only.
 *
 * <p>The 26.3 bytecode inventory confirms three calls:
 * BuildContexts -> ContextChain.runModifier;
 * ExecuteCommand -> ContextChain.runExecutable;
 * ContextChain.runExecutable -> Command.run.
 *
 * <p>A phase is selected only if its enclosing BuildContexts or ExecuteCommand
 * task was selected by the existing fixed 1/32 ordinal hash. EMPTY reads two
 * consecutive clocks immediately before the original call; TIMED brackets it.
 * All observations are inclusive and must not be added as disjoint cost.
 */
public final class SchedulerPhaseCpuProbe {
    public enum Phase {
        MODIFIER(SchedulerTaskCpuProbe.Path.BUILD),
        EXECUTABLE(SchedulerTaskCpuProbe.Path.EXECUTE),
        COMMAND(SchedulerTaskCpuProbe.Path.EXECUTE),
        COPY(SchedulerTaskCpuProbe.Path.EXECUTE),
        RESULT(SchedulerTaskCpuProbe.Path.EXECUTE);

        private final SchedulerTaskCpuProbe.Path parent;
        Phase(SchedulerTaskCpuProbe.Path parent) { this.parent = parent; }
    }

    public enum Mode { OFF, EMPTY, TIMED }

    public static final long SKIP = Long.MIN_VALUE;
    private static final long NESTED = Long.MIN_VALUE + 1;
    private static final Mode MODE = fromEnvironment();
    private static final boolean PLUMBING_ENABLED = Boolean.parseBoolean(
            System.getenv("FC_SCHED_BRIGADIER_PLUMBING_PROBE"));
    private static final ThreadMXBean CLOCK =
            MODE == Mode.OFF ? null : ManagementFactory.getThreadMXBean();
    private static final Stats[] STATS = new Stats[Phase.values().length];
    private static long ownerThreadId = -1L;

    static {
        for (int i = 0; i < STATS.length; i++) STATS[i] = new Stats();
    }

    private static final class Stats {
        long calls;
        long samples;
        long cpuNs;
        long zeros;
        long nested;
        int depth;
        long copyReused;
        long copyAllocated;
        long callbackSuccess;
        long callbackFailure;
    }

    private SchedulerPhaseCpuProbe() {}

    private static Mode fromEnvironment() {
        String raw = System.getenv("FC_SCHED_PHASE_CPU_PROBE");
        if (raw == null || raw.isBlank() || "off".equalsIgnoreCase(raw)) return Mode.OFF;
        return switch (raw.toLowerCase(Locale.ROOT)) {
            case "empty" -> Mode.EMPTY;
            case "timed" -> Mode.TIMED;
            default -> throw new IllegalArgumentException(
                    "FC_SCHED_PHASE_CPU_PROBE must be off, empty, or timed");
        };
    }

    public static boolean enabled() { return MODE != Mode.OFF; }
    public static String modeName() { return MODE.name().toLowerCase(Locale.ROOT); }
    public static boolean clockReady() {
        return enabled() && CLOCK.isCurrentThreadCpuTimeSupported()
                && CLOCK.isThreadCpuTimeEnabled();
    }

    public static void ensureReady() {
        if (MODE == Mode.OFF) return;
        if (PLUMBING_ENABLED && !SchedulerPathCensus.enabled()) {
            throw new IllegalStateException("Brigadier plumbing probe requires event census");
        }
        SchedulerTaskCpuProbe.ensureReady();
        if (!SchedulerTaskCpuProbe.modeName().equals(modeName())) {
            throw new IllegalStateException(
                    "Phase CPU probe mode differs from enclosing task CPU probe mode");
        }
        if (!clockReady() || CLOCK.getCurrentThreadCpuTime() < 0L) {
            throw new IllegalStateException("Phase CPU current Server-thread clock unavailable");
        }
    }

    private static long cpuTime() {
        long cpu = CLOCK.getCurrentThreadCpuTime();
        if (cpu < 0L) throw new IllegalStateException("Current-thread CPU clock returned -1");
        return cpu;
    }

    /**
     * An event scope is established by SchedulerPathCensus and sampling
     * selection by the already-approved task CPU probe.
     */
    public static long begin(Phase phase) {
        if (MODE == Mode.OFF
                || ((phase == Phase.COPY || phase == Phase.RESULT) && !PLUMBING_ENABLED)
                || !SchedulerTaskCpuProbe.activeSampled(phase.parent)) return SKIP;

        Stats stat = STATS[phase.ordinal()];
        stat.calls++;
        if (stat.depth != 0) {
            stat.nested++;
            stat.depth++;
            return NESTED;
        }
        stat.depth = 1;
        long tid = Thread.currentThread().threadId();
        if (!"Server thread".equals(Thread.currentThread().getName())) {
            throw new IllegalStateException("Phase CPU probe outside Server thread");
        }
        if (ownerThreadId == -1L) ownerThreadId = tid;
        else if (ownerThreadId != tid) {
            throw new IllegalStateException("Phase CPU probe changed thread identity");
        }

        if (MODE == Mode.EMPTY) {
            long started = cpuTime();
            record(stat, cpuTime() - started);
            return 0L;
        }
        return cpuTime();
    }

    public static void end(Phase phase, long token) {
        endWithDuration(phase, token);
    }

    /**
     * Returns raw inclusive CPU nanos only for a selected TIMED scope,
     * otherwise -1. Shared timer/counter semantics remain unchanged.
     * Caller may classify the source delegate AFTER this interval closes.
     */
    public static long endWithDuration(Phase phase, long token) {
        if (token == SKIP) return -1L;
        Stats stat = STATS[phase.ordinal()];
        if (token == NESTED) {
            if (stat.depth < 2) throw new IllegalStateException("Nested phase stack unbalanced");
            stat.depth--;
            return -1L;
        }
        if (stat.depth != 1) throw new IllegalStateException("Phase scope leaked or unbalanced");
        long elapsed = -1L;
        if (MODE == Mode.TIMED) {
            elapsed = cpuTime() - token;
            record(stat, elapsed);
        }
        stat.depth = 0;
        return elapsed;
    }

    /**
     * Diagnostic categories on selected calls only. copyFor may return the
     * exact existing context (same-source fast path) or allocate a shallow
     * copy. Success and failure use separate bytecode callback callsites.
     */
    public static void observedCopy(long token, boolean reused) {
        if (token == SKIP || token == NESTED) return;
        Stats stat = STATS[Phase.COPY.ordinal()];
        if (reused) stat.copyReused++;
        else stat.copyAllocated++;
    }

    public static void observedResult(long token, boolean success) {
        if (token == SKIP || token == NESTED) return;
        Stats stat = STATS[Phase.RESULT.ordinal()];
        if (success) stat.callbackSuccess++;
        else stat.callbackFailure++;
    }

    private static void record(Stats stat, long ns) {
        if (ns < 0) throw new IllegalStateException("Server-thread CPU clock regressed");
        stat.samples = Math.addExact(stat.samples, 1L);
        stat.cpuNs = Math.addExact(stat.cpuNs, ns);
        if (ns == 0) stat.zeros++;
    }

    private static Stats stat(Phase p) { return STATS[p.ordinal()]; }
    public static long ownerThreadId() { return ownerThreadId; }
    public static long calls(Phase p) { return stat(p).calls; }
    public static long samples(Phase p) { return stat(p).samples; }
    public static long cpuNs(Phase p) { return stat(p).cpuNs; }
    public static long zeroDeltas(Phase p) { return stat(p).zeros; }
    public static long nested(Phase p) { return stat(p).nested; }
    public static int depth(Phase p) { return stat(p).depth; }
    public static long copyReused() { return stat(Phase.COPY).copyReused; }
    public static long copyAllocated() { return stat(Phase.COPY).copyAllocated; }
    public static long resultSuccess() { return stat(Phase.RESULT).callbackSuccess; }
    public static long resultFailure() { return stat(Phase.RESULT).callbackFailure; }
    public static boolean plumbingEnabled() { return PLUMBING_ENABLED; }
}
