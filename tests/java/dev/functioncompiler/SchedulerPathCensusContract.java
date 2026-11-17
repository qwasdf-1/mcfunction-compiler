package dev.functioncompiler;

/** Plain Java contract: event-window task-path counters never spill across sessions. */
public final class SchedulerPathCensusContract {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        Thread.currentThread().setName("Server thread");
        String expected = args[0];
        check(SchedulerPathCensus.enabled() == expected.equals("on"), "enable flag");
        if (expected.equals("off")) {
            SchedulerPathCensus.queueEntry();
            SchedulerPathCensus.buildContexts();
            check(SchedulerPathCensus.queueEntriesCount() == 0, "disabled counter leaked");
            check(SchedulerPathCensus.buildContextsCount() == 0, "disabled task counter leaked");
            System.out.println("mode=off valid=true");
            return;
        }
        SchedulerPathCensus.queueEntry(); // before event: excluded
        SchedulerPathCensus.begin();
        SchedulerPathCensus.queueEntry();
        SchedulerPathCensus.queueEntry();
        SchedulerPathCensus.buildContexts();
        SchedulerPathCensus.executeCommand();
        SchedulerPathCensus.callFunction();
        SchedulerPathCensus.continuation();
        SchedulerPathCensus.end();
        SchedulerPathCensus.queueEntry(); // after event: excluded
        check(!SchedulerPathCensus.recording(), "scope leaked");
        check(SchedulerPathCensus.sessionsStarted() == 1, "begin count");
        check(SchedulerPathCensus.sessionsStopped() == 1, "end count");
        check(SchedulerPathCensus.queueEntriesCount() == 2, "queue count");
        check(SchedulerPathCensus.buildContextsCount() == 1, "build count");
        check(SchedulerPathCensus.executeCommandCount() == 1, "leaf count");
        check(SchedulerPathCensus.callFunctionCount() == 1, "function count");
        check(SchedulerPathCensus.continuationCount() == 1, "continuation count");
        check(SchedulerPathCensus.ownerThreadId()
              == Thread.currentThread().threadId(), "wrong server thread");
        System.out.println("mode=on valid=true");
    }
}
