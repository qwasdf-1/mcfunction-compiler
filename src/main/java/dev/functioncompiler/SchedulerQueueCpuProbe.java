package dev.functioncompiler;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.Locale;

/**
 * SCHED-ATTR-023 research-only Server-thread CPU accounting at two nested
 * boundaries: entire ExecutionContext.runCommandQueue, and each
 * CommandQueueEntry.execute. Their difference is queue-loop time including
 * measurement overhead, NOT all scheduler CPU or a recoverable speedup.
 *
 * <p>Both active modes perform the same number of CPU clock reads at each
 * observed boundary: EMPTY reads them consecutively before real work,
 * TIMED brackets the real work. All counters belong to one Server thread.
 * The begin/end command activates only the native-event diagnostic window.
 */
public final class SchedulerQueueCpuProbe {
    public enum Mode { OFF, EMPTY, TIMED }

    private static final Mode MODE = modeFromEnvironment();
    private static final ThreadMXBean CPU_CLOCK =
            MODE == Mode.OFF ? null : ManagementFactory.getThreadMXBean();

    private static boolean recording;
    private static long ownerThreadId = -1;
    private static long begins;
    private static long ends;
    private static int queueDepth;
    private static int entryDepth;
    private static long nestedQueueEntries;
    private static long nestedCommandEntries;
    private static boolean queueArmed;
    private static long queueStartedNanos;
    private static long entryStartedNanos;

    private static long queueSamples;
    private static long entrySamples;
    private static long queueCpuNanos;
    private static long entryCpuNanos;
    private static long queueZeroDelta;
    private static long entryZeroDelta;

    private SchedulerQueueCpuProbe() {
    }

    private static Mode modeFromEnvironment() {
        String setting = System.getenv("FC_SCHED_QUEUE_CPU_PROBE");
        if (setting == null || setting.isBlank() || "off".equalsIgnoreCase(setting)) {
            return Mode.OFF;
        }
        return switch (setting.toLowerCase(Locale.ROOT)) {
            case "empty" -> Mode.EMPTY;
            case "timed" -> Mode.TIMED;
            default -> throw new IllegalArgumentException(
                    "FC_SCHED_QUEUE_CPU_PROBE must be off, empty or timed");
        };
    }

    public static boolean enabled() {
        return MODE != Mode.OFF;
    }

    public static String modeName() {
        return MODE.name().toLowerCase(Locale.ROOT);
    }

    public static boolean clockReady() {
        return enabled()
                && CPU_CLOCK.isCurrentThreadCpuTimeSupported()
                && CPU_CLOCK.isThreadCpuTimeEnabled();
    }

    public static void requireReady() {
        if (!enabled()) {
            return;
        }
        if (!clockReady() || CPU_CLOCK.getCurrentThreadCpuTime() < 0) {
            throw new IllegalStateException(
                    "SchedulerQueueCpuProbe needs an already enabled Server-thread CPU clock");
        }
        for (String flag : new String[] {
                "FC_RUNTIME_TRACE", "FC_COMMAND_CALLBACK_METRICS",
                "FC_SCHED_ARCH_COUNTERS", "FC_SCORE_ADD_TIMING",
                "FC_SCORE_ADD_METRICS", "FC_SCORE_ADD_PHASE_TIMERS",
                "FC_SCORE_ADD_CPU_PROBE", "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS"}) {
            String setting = System.getenv(flag);
            if (setting != null && !setting.equalsIgnoreCase("off")
                    && !setting.equalsIgnoreCase("false")
                    && !setting.isBlank()) {
                throw new IllegalStateException(
                        "Queue CPU probe cannot run with " + flag + " enabled");
            }
        }
    }

    private static void checkThread() {
        long threadId = Thread.currentThread().threadId();
        if (!"Server thread".equals(Thread.currentThread().getName())) {
            throw new IllegalStateException("Queue CPU probe outside Minecraft Server thread");
        }
        if (ownerThreadId == -1) {
            ownerThreadId = threadId;
        } else if (ownerThreadId != threadId) {
            throw new IllegalStateException("Queue CPU probe changed Java thread");
        }
    }

    private static long cpuTime() {
        long value = CPU_CLOCK.getCurrentThreadCpuTime();
        if (value < 0) {
            throw new IllegalStateException("Server-thread CPU clock returned -1");
        }
        return value;
    }

    private static long elapsed(long begin, long end) {
        if (end < begin) {
            throw new IllegalStateException("Server-thread CPU clock regressed");
        }
        return end - begin;
    }

    private static long checkedAdd(long a, long b) {
        return Math.addExact(a, b);
    }

    public static void begin() {
        if (enabled()) {
            requireReady();
            checkThread();
        }
        if (recording || begins != ends || queueDepth != 0 || entryDepth != 0) {
            throw new IllegalStateException("Queue CPU probe already active or nested");
        }
        recording = true;
        begins++;
    }

    public static void end() {
        if (!recording || begins != ends + 1) {
            throw new IllegalStateException("Queue CPU probe not active");
        }
        if (enabled()) {
            checkThread();
        }
        // end() runs inside the final RCON queue entry. That queue and entry
        // still close normally after the flag is disabled, and are counted.
        recording = false;
        ends++;
    }

    public static void queueEnter() {
        if (!enabled() || !recording) {
            return;
        }
        checkThread();
        queueDepth++;
        if (queueDepth != 1) {
            nestedQueueEntries++;
            return;
        }
        queueArmed = true;
        if (MODE == Mode.EMPTY) {
            long started = cpuTime();
            recordQueue(elapsed(started, cpuTime()));
        } else {
            queueStartedNanos = cpuTime();
        }
    }

    public static void queueExit() {
        if (!enabled() || queueDepth == 0) {
            return;
        }
        if (queueDepth > 1) {
            queueDepth--;
            return;
        }
        if (queueArmed && MODE == Mode.TIMED) {
            recordQueue(elapsed(queueStartedNanos, cpuTime()));
        }
        queueArmed = false;
        queueDepth = 0;
    }

    public static void entryEnter() {
        if (!enabled() || !queueArmed) {
            return;
        }
        checkThread();
        entryDepth++;
        if (entryDepth != 1) {
            nestedCommandEntries++;
            return;
        }
        if (MODE == Mode.EMPTY) {
            long started = cpuTime();
            recordEntry(elapsed(started, cpuTime()));
        } else {
            entryStartedNanos = cpuTime();
        }
    }

    public static void entryExit() {
        if (!enabled() || entryDepth == 0) {
            return;
        }
        if (entryDepth > 1) {
            entryDepth--;
            return;
        }
        if (MODE == Mode.TIMED) {
            recordEntry(elapsed(entryStartedNanos, cpuTime()));
        }
        entryDepth = 0;
    }

    private static void recordQueue(long nanos) {
        queueSamples = checkedAdd(queueSamples, 1L);
        queueCpuNanos = checkedAdd(queueCpuNanos, nanos);
        if (nanos == 0) {
            queueZeroDelta++;
        }
    }

    private static void recordEntry(long nanos) {
        entrySamples = checkedAdd(entrySamples, 1L);
        entryCpuNanos = checkedAdd(entryCpuNanos, nanos);
        if (nanos == 0) {
            entryZeroDelta++;
        }
    }

    public static long begins() { return begins; }
    public static long ends() { return ends; }
    public static boolean recording() { return recording; }
    public static long ownerThreadId() { return ownerThreadId; }
    public static int queueDepth() { return queueDepth; }
    public static int entryDepth() { return entryDepth; }
    public static long nestedQueueEntries() { return nestedQueueEntries; }
    public static long nestedCommandEntries() { return nestedCommandEntries; }
    public static long queueSamples() { return queueSamples; }
    public static long entrySamples() { return entrySamples; }
    public static long queueCpuNanos() { return queueCpuNanos; }
    public static long entryCpuNanos() { return entryCpuNanos; }
    public static long queueZeroDelta() { return queueZeroDelta; }
    public static long entryZeroDelta() { return entryZeroDelta; }
}
