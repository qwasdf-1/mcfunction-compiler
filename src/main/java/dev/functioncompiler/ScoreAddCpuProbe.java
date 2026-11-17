package dev.functioncompiler;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;

/**
 * SCHED-COMP-022 only: attribute on-CPU time to the typed ScoreAdd callback.
 *
 * <p>Each enabled mode performs exactly two ThreadMXBean reads and one sample
 * accumulation per typed callback. EMPTY measures a back-to-back clock-read
 * interval before executing the unchanged callback; TIMED brackets the callback.
 * Counters are Server-thread-local-by-contract, plain longs, and are queried
 * only outside the measured event. No feature is enabled without an explicit
 * process environment opt-in.
 */
final class ScoreAddCpuProbe {
    enum Mode { OFF, EMPTY, TIMED }

    private static final Mode MODE = readMode(System.getenv("FC_SCORE_ADD_CPU_PROBE"));
    private static final ThreadMXBean CPU_CLOCK =
            MODE == Mode.OFF ? null : ManagementFactory.getThreadMXBean();
    private static long ownerThreadId = -1L;
    private static long calls;
    private static long totalCpuNanos;
    private static long directSuccesses;
    private static long zeroDeltaCalls;

    private ScoreAddCpuProbe() {
    }

    private static Mode readMode(String value) {
        if (value == null || value.isBlank() || value.equalsIgnoreCase("off")) {
            return Mode.OFF;
        }
        return switch (value.toLowerCase(java.util.Locale.ROOT)) {
            case "empty" -> Mode.EMPTY;
            case "timed" -> Mode.TIMED;
            default -> throw new IllegalArgumentException(
                    "FC_SCORE_ADD_CPU_PROBE must be off, empty or timed");
        };
    }

    static boolean enabled() {
        return MODE != Mode.OFF;
    }

    static Mode mode() {
        return MODE;
    }

    static String modeName() {
        return MODE.name().toLowerCase(java.util.Locale.ROOT);
    }

    static boolean clockSupportedAndEnabled() {
        return enabled()
                && CPU_CLOCK.isCurrentThreadCpuTimeSupported()
                && CPU_CLOCK.isThreadCpuTimeEnabled();
    }

    private static void requireServerThread() {
        long id = Thread.currentThread().threadId();
        if (ownerThreadId == -1L) {
            ownerThreadId = id;
        } else if (ownerThreadId != id) {
            throw new IllegalStateException("ScoreAddCpuProbe changed Java thread");
        }
    }

    static void ensureReady() {
        if (!enabled()) {
            return;
        }
        // CPU clock must already be active. Do not silently switch it on,
        // because doing so could perturb treatment and control differently.
        if (!clockSupportedAndEnabled()) {
            throw new IllegalStateException("ThreadMXBean current-thread CPU time unavailable");
        }
        if (CPU_CLOCK.getCurrentThreadCpuTime() < 0) {
            throw new IllegalStateException("ThreadMXBean CPU clock returned -1");
        }
    }

    static long begin() {
        if (!enabled()) {
            throw new IllegalStateException("CPU probe is not enabled");
        }
        requireServerThread();
        long nanos = CPU_CLOCK.getCurrentThreadCpuTime();
        if (nanos < 0) {
            throw new IllegalStateException("CPU clock unavailable during callback");
        }
        return nanos;
    }

    static void end(long started) {
        long finished = CPU_CLOCK.getCurrentThreadCpuTime();
        if (finished < started) {
            throw new IllegalStateException("CPU clock regressed or became unavailable");
        }
        long delta = finished - started;
        if (Long.MAX_VALUE - totalCpuNanos < delta || calls == Long.MAX_VALUE) {
            throw new ArithmeticException("CPU probe counters overflowed");
        }
        calls++;
        totalCpuNanos += delta;
        if (delta == 0) {
            zeroDeltaCalls++;
        }
    }

    static void directSuccess() {
        if (!enabled()) {
            return;
        }
        directSuccesses++;
    }

    static long calls() {
        return calls;
    }

    static long totalCpuNanos() {
        return totalCpuNanos;
    }

    static long directSuccesses() {
        return directSuccesses;
    }

    static long zeroDeltaCalls() {
        return zeroDeltaCalls;
    }

    static long ownerThreadId() {
        return ownerThreadId;
    }
}
