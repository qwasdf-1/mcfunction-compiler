package dev.functioncompiler;

/** Plain-JDK opt-in CPU clock contract without a Minecraft dependency. */
public final class SchedulerQueueCpuProbeContract {
    private static volatile long sink;

    private static void check(boolean predicate, String explanation) {
        if (!predicate) {
            throw new AssertionError(explanation);
        }
    }

    private static void work() {
        long value = sink;
        for (int i = 0; i < 512; i++) {
            value = (value + 11) * 17L;
        }
        sink = value;
    }

    public static void main(String[] args) {
        Thread.currentThread().setName("Server thread");
        String mode = args[0];
        check(SchedulerQueueCpuProbe.modeName().equals(mode), "wrong probe mode");
        if (!mode.equals("off")) {
            SchedulerQueueCpuProbe.requireReady();
            check(SchedulerQueueCpuProbe.clockReady(), "CPU clock disabled");
        }

        SchedulerQueueCpuProbe.begin();
        for (int q = 0; q < 100; q++) {
            SchedulerQueueCpuProbe.queueEnter();
            for (int e = 0; e < 5; e++) {
                SchedulerQueueCpuProbe.entryEnter();
                work();
                SchedulerQueueCpuProbe.entryExit();
            }
            SchedulerQueueCpuProbe.queueExit();
        }
        // Simulate an RCON end command that disables recording from inside
        // its own dequeued entry, which must still contribute to both timers.
        SchedulerQueueCpuProbe.queueEnter();
        SchedulerQueueCpuProbe.entryEnter();
        SchedulerQueueCpuProbe.end();
        SchedulerQueueCpuProbe.entryExit();
        SchedulerQueueCpuProbe.queueExit();

        check(!SchedulerQueueCpuProbe.recording(), "recording leaked");
        check(SchedulerQueueCpuProbe.begins() == 1
              && SchedulerQueueCpuProbe.ends() == 1, "capture window mismatch");
        check(SchedulerQueueCpuProbe.queueDepth() == 0
              && SchedulerQueueCpuProbe.entryDepth() == 0, "unclosed depth");
        check(SchedulerQueueCpuProbe.nestedQueueEntries() == 0
              && SchedulerQueueCpuProbe.nestedCommandEntries() == 0, "unexpected nesting");
        if (mode.equals("off")) {
            check(SchedulerQueueCpuProbe.queueSamples() == 0, "off queue sample");
            check(SchedulerQueueCpuProbe.entrySamples() == 0, "off entry sample");
        } else {
            check(SchedulerQueueCpuProbe.queueSamples() == 101, "queue count");
            check(SchedulerQueueCpuProbe.entrySamples() == 501, "entry count");
            check(SchedulerQueueCpuProbe.queueCpuNanos() >= 0, "queue clock");
            check(SchedulerQueueCpuProbe.entryCpuNanos() >= 0, "entry clock");
            check(SchedulerQueueCpuProbe.queueZeroDelta() <= 101, "queue zero count");
            check(SchedulerQueueCpuProbe.entryZeroDelta() <= 501, "entry zero count");
            check(SchedulerQueueCpuProbe.ownerThreadId()
                    == Thread.currentThread().threadId(), "CPU clock thread mismatch");
            if (mode.equals("timed")) {
                check(SchedulerQueueCpuProbe.queueCpuNanos()
                      >= SchedulerQueueCpuProbe.entryCpuNanos(),
                      "negative measured queue-loop residual");
            }
        }
        System.out.println("mode=" + mode + " valid=true");
    }
}
