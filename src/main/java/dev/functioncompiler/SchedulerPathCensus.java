package dev.functioncompiler;

/**
 * Research-only event-window census of vanilla execution-task method entries.
 *
 * Counts method invocations rather than elapsed time. A method may schedule
 * another task; these counters are not an exclusive CPU breakdown and must
 * not be summed as independent work without confirming queue-entry coverage.
 */
public final class SchedulerPathCensus {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_SCHED_PATH_CENSUS"));
    private static boolean recording;
    private static long ownerThreadId = -1L;
    private static long sessionsStarted;
    private static long sessionsStopped;
    private static long queueEntries;
    private static long buildContexts;
    private static long executeCommand;
    private static long callFunction;
    private static long continuation;

    private SchedulerPathCensus() {}

    public static boolean enabled() { return ENABLED; }
    public static boolean recording() { return recording; }

    private static void checkThread() {
        Thread thread = Thread.currentThread();
        if (!"Server thread".equals(thread.getName())) {
            throw new IllegalStateException("SchedulerPathCensus requires Minecraft Server thread");
        }
        if (ownerThreadId == -1L) {
            ownerThreadId = thread.threadId();
        } else if (thread.threadId() != ownerThreadId) {
            throw new IllegalStateException("SchedulerPathCensus owner thread changed");
        }
    }

    public static void begin() {
        if (!ENABLED) {
            throw new IllegalStateException("SchedulerPathCensus is disabled");
        }
        checkThread();
        if (recording || sessionsStarted != sessionsStopped) {
            throw new IllegalStateException("SchedulerPathCensus was already recording");
        }
        recording = true;
        sessionsStarted++;
    }

    public static void end() {
        if (!ENABLED) {
            throw new IllegalStateException("SchedulerPathCensus is disabled");
        }
        checkThread();
        if (!recording || sessionsStarted != sessionsStopped + 1) {
            throw new IllegalStateException("SchedulerPathCensus was not recording");
        }
        recording = false;
        sessionsStopped++;
    }

    public static void queueEntry() {
        if (ENABLED && recording) { queueEntries++; }
    }
    public static void buildContexts() {
        if (ENABLED && recording) { buildContexts++; }
    }
    public static void executeCommand() {
        if (ENABLED && recording) { executeCommand++; }
    }
    public static void callFunction() {
        if (ENABLED && recording) { callFunction++; }
    }
    public static void continuation() {
        if (ENABLED && recording) { continuation++; }
    }

    public static long ownerThreadId() { return ownerThreadId; }
    public static long sessionsStarted() { return sessionsStarted; }
    public static long sessionsStopped() { return sessionsStopped; }
    public static long queueEntriesCount() { return queueEntries; }
    public static long buildContextsCount() { return buildContexts; }
    public static long executeCommandCount() { return executeCommand; }
    public static long callFunctionCount() { return callFunction; }
    public static long continuationCount() { return continuation; }
}
