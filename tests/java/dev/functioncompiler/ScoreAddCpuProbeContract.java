package dev.functioncompiler;

/** Compile and launch outside Minecraft to exercise ScoreAddCpuProbe modes. */
public final class ScoreAddCpuProbeContract {
    private static volatile long blackhole;

    private static void check(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static void actualWork() {
        long value = blackhole;
        for (int i = 0; i < 200; i++) {
            value += i * 13L + 1;
        }
        blackhole = value;
    }

    public static void main(String[] args) {
        String expected = args[0];
        check(ScoreAddCpuProbe.modeName().equals(expected), "mode mismatch");
        if (expected.equals("off")) {
            check(!ScoreAddCpuProbe.enabled(), "off unexpectedly enabled");
            check(ScoreAddCpuProbe.calls() == 0, "off started counting");
            System.out.println("mode=off valid=true");
            return;
        }

        check(ScoreAddCpuProbe.enabled(), "opt-in mode not enabled");
        ScoreAddCpuProbe.ensureReady();
        check(ScoreAddCpuProbe.clockSupportedAndEnabled(), "thread CPU clock unavailable");
        for (int i = 0; i < 1000; i++) {
            if (ScoreAddCpuProbe.mode() == ScoreAddCpuProbe.Mode.EMPTY) {
                long started = ScoreAddCpuProbe.begin();
                ScoreAddCpuProbe.end(started);
                actualWork();
            } else {
                long started = ScoreAddCpuProbe.begin();
                try {
                    actualWork();
                } finally {
                    ScoreAddCpuProbe.end(started);
                }
            }
            ScoreAddCpuProbe.directSuccess();
        }
        check(ScoreAddCpuProbe.calls() == 1000, "callback total");
        check(ScoreAddCpuProbe.directSuccesses() == 1000, "direct success total");
        check(ScoreAddCpuProbe.totalCpuNanos() >= 0, "negative CPU total");
        check(ScoreAddCpuProbe.ownerThreadId() == Thread.currentThread().threadId(),
                "wrong owner thread");
        check(ScoreAddCpuProbe.zeroDeltaCalls() <= 1000, "invalid zero count");
        System.out.println("mode=" + expected + " valid=true");
    }
}
