package dev.functioncompiler;

/** Plain JDK contract, no Minecraft dependencies, same ordinal-selected tasks. */
public final class SchedulerPhaseCpuProbeContract {
    private static volatile long sink;

    private static void check(boolean value, String note) {
        if (!value) throw new AssertionError(note);
    }
    private static void work() {
        long result = sink;
        for (int j = 0; j < 400; j++) result = (result + j * 17L) * 19L;
        sink = result;
    }
    private static void runPhase(SchedulerPhaseCpuProbe.Phase phase) {
        long started = SchedulerPhaseCpuProbe.begin(phase);
        try {
            work();
        } finally {
            SchedulerPhaseCpuProbe.end(phase, started);
        }
    }

    public static void main(String[] args) {
        Thread.currentThread().setName("Server thread");
        String mode = args[0];
        check(SchedulerPhaseCpuProbe.modeName().equals(mode), "phase mode mismatch");
        if (!mode.equals("off")) {
            SchedulerTaskCpuProbe.ensureReady();
            SchedulerPhaseCpuProbe.ensureReady();
        }
        SchedulerPathCensus.begin();
        for (int i = 0; i < 20000; i++) {
            SchedulerTaskCpuProbe.enter(SchedulerTaskCpuProbe.Path.BUILD);
            runPhase(SchedulerPhaseCpuProbe.Phase.MODIFIER);
            SchedulerTaskCpuProbe.exit(SchedulerTaskCpuProbe.Path.BUILD);

            SchedulerTaskCpuProbe.enter(SchedulerTaskCpuProbe.Path.EXECUTE);
            long outer = SchedulerPhaseCpuProbe.begin(SchedulerPhaseCpuProbe.Phase.EXECUTABLE);
            try {
                runPhase(SchedulerPhaseCpuProbe.Phase.COMMAND);
            } finally {
                SchedulerPhaseCpuProbe.end(SchedulerPhaseCpuProbe.Phase.EXECUTABLE, outer);
            }
            SchedulerTaskCpuProbe.exit(SchedulerTaskCpuProbe.Path.EXECUTE);
        }
        SchedulerPathCensus.end();
        check(!SchedulerPathCensus.recording(), "session leaked");
        for (SchedulerPhaseCpuProbe.Phase phase : SchedulerPhaseCpuProbe.Phase.values()) {
            long samples = SchedulerPhaseCpuProbe.samples(phase);
            check(SchedulerPhaseCpuProbe.depth(phase) == 0, "scope leaked");
            check(SchedulerPhaseCpuProbe.nested(phase) == 0, "nested same phase");
            if (mode.equals("off")) {
                check(samples == 0, "disabled mode sampled CPU");
            } else {
                check(samples > 450 && samples < 800, "wrong 1/32 parent selection");
                check(samples == SchedulerPhaseCpuProbe.calls(phase), "missing clock close");
                check(SchedulerPhaseCpuProbe.zeroDeltas(phase) <= samples, "bad zero count");
                check(SchedulerPhaseCpuProbe.cpuNs(phase) >= 0, "negative CPU ns");
            }
        }
        check(SchedulerPhaseCpuProbe.samples(SchedulerPhaseCpuProbe.Phase.EXECUTABLE)
              == SchedulerPhaseCpuProbe.samples(SchedulerPhaseCpuProbe.Phase.COMMAND),
              "Nested executable and command selection not aligned");
        if (!mode.equals("off")) {
            check(SchedulerPhaseCpuProbe.ownerThreadId()
                  == Thread.currentThread().threadId(), "wrong clock thread");
        }
        System.out.println("mode=" + mode + " valid=true");
    }
}
