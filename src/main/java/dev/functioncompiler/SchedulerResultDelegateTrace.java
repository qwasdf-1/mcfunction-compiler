package dev.functioncompiler;

import java.util.LinkedHashMap;
import java.util.Map;

import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.ExecutionCommandSource;

/**
 * SCHED-ATTR-028: event-only, bounded dynamic delegate-class census.
 *
 * Only the existing 1-in-32 selected ExecuteCommand result callbacks are
 * classified. Classification happens AFTER the prior CPU clock interval
 * closes, so class-name lookup/hash-table maintenance is never charged to the
 * measured callback. Class names identify runtime lambdas by their declaring
 * class prefix, not individual lambda site/effect or nested chain members.
 */
public final class SchedulerResultDelegateTrace {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_SCHED_RESULT_DELEGATE_TRACE"));
    private static final int MAX_TYPES = 14;
    private static final String OVERFLOW = "OTHER";
    private static final LinkedHashMap<String, Bucket> TYPES = new LinkedHashMap<>();
    private static long observed;
    private static long rawCpuNanos;
    private static long rawTimedSamples;
    private static long successes;
    private static long failures;
    private static long ownerThreadId = -1L;
    private static long nonSource;

    private static final class Bucket {
        long calls;
        long rawCpuNs;
        long timedSamples;
        long successes;
        long failures;
    }

    private SchedulerResultDelegateTrace() {}

    public static boolean enabled() { return ENABLED; }

    private static String nameFor(Object source) {
        if (!(source instanceof ExecutionCommandSource<?> commandSource)) {
            nonSource++;
            return "NON_EXECUTION_SOURCE";
        }
        CommandResultCallback callback = commandSource.callback();
        if (callback == null) return "NULL";
        if (callback == CommandResultCallback.EMPTY) return "EMPTY";
        String name = callback.getClass().getName();
        int hiddenSuffix = name.indexOf('/');
        if (hiddenSuffix >= 0) name = name.substring(0, hiddenSuffix);
        // Lambda site class names can be generated uniquely per JVM; use the
        // declaring owner, but do not pretend this isolates chain members.
        int lambda = name.indexOf("$$Lambda");
        if (lambda >= 0) name = name.substring(0, lambda) + "$$Lambda";
        return name.replace(" ", "_").replace(",", "_").replace("|", "_");
    }

    /**
     * @param token start token of a previously selected RESULT phase; SKIP
     *              means no selection, and never adds a data row.
     * @param rawNs measured inclusive clock nanos, or -1 in EMPTY arm.
     */
    public static void observe(Object source, boolean success, long token, long rawNs) {
        if (!ENABLED || token == SchedulerPhaseCpuProbe.SKIP
                || token == SchedulerPhaseCpuProbe.NESTED) return;
        // A selected final RCON stop command can end the event census before
        // its own result callback. The selected timing token, not the
        // now-closed window flag, proves this observation belongs to scope.
        if (!"Server thread".equals(Thread.currentThread().getName())) {
            throw new IllegalStateException("Delegate census ran outside Server thread");
        }
        long tid = Thread.currentThread().threadId();
        if (ownerThreadId < 0) ownerThreadId = tid;
        else if (ownerThreadId != tid) {
            throw new IllegalStateException("Delegate census changed Server thread");
        }

        String name = nameFor(source);
        Bucket bucket = TYPES.get(name);
        if (bucket == null) {
            if (TYPES.size() >= MAX_TYPES) {
                name = OVERFLOW;
                bucket = TYPES.get(name);
            }
            if (bucket == null) {
                bucket = new Bucket();
                TYPES.put(name, bucket);
            }
        }
        bucket.calls++;
        observed++;
        if (success) {
            successes++;
            bucket.successes++;
        } else {
            failures++;
            bucket.failures++;
        }
        if (rawNs >= 0) {
            rawTimedSamples++;
            rawCpuNanos = Math.addExact(rawCpuNanos, rawNs);
            bucket.timedSamples++;
            bucket.rawCpuNs = Math.addExact(bucket.rawCpuNs, rawNs);
        }
    }

    /**
     * Standalone research-only RCON command, separate from the already-truncated
     * generic probe status. All output fields are short, stable and parseable.
     * Example: FC_SCHED_DELEGATES mode=timed calls=872 ... types=name|n|ns|s|f;...
     */
    public static String summary() {
        StringBuilder out = new StringBuilder("FC_SCHED_DELEGATES");
        out.append(" enabled=").append(ENABLED);
        out.append(" mode=").append(SchedulerPhaseCpuProbe.modeName());
        out.append(" thread=").append(ownerThreadId);
        out.append(" calls=").append(observed);
        out.append(" timed_samples=").append(rawTimedSamples);
        out.append(" raw_cpu_ns=").append(rawCpuNanos);
        out.append(" success=").append(successes);
        out.append(" failure=").append(failures);
        out.append(" non_source=").append(nonSource);
        out.append(" types=");
        boolean first = true;
        for (Map.Entry<String, Bucket> entry : TYPES.entrySet()) {
            if (!first) out.append(';');
            first = false;
            Bucket b = entry.getValue();
            out.append(entry.getKey()).append('|').append(b.calls)
                    .append('|').append(b.rawCpuNs)
                    .append('|').append(b.timedSamples)
                    .append('|').append(b.successes)
                    .append('|').append(b.failures);
        }
        if (out.length() > 3300) {
            throw new IllegalStateException("RCON delegate summary exceeded safe payload budget");
        }
        return out.toString();
    }
}
