package dev.functioncompiler;

/** JDK-only calibration contract for sparse CPU sampling (no Minecraft). */
public final class SchedulerTaskCpuProbeContract {
    private static volatile long sink;
    private static void check(boolean b,String msg) {
        if (!b) throw new AssertionError(msg);
    }
    private static void work() {
        long x=sink;
        for (int i=0;i<500;i++) x=(x+13L)*(i+5L);
        sink=x;
    }
    public static void main(String[] args) {
        Thread.currentThread().setName("Server thread");
        String mode=args[0];
        check(SchedulerTaskCpuProbe.modeName().equals(mode),"mode mismatch");
        if (!mode.equals("off")) SchedulerTaskCpuProbe.ensureReady();
        SchedulerPathCensus.begin();
        for (int i=0;i<20000;i++) {
            for (var p:SchedulerTaskCpuProbe.Path.values()) {
                SchedulerTaskCpuProbe.enter(p);
                work();
                SchedulerTaskCpuProbe.exit(p);
            }
        }
        SchedulerPathCensus.end();
        for (var p:SchedulerTaskCpuProbe.Path.values()) {
            check(SchedulerTaskCpuProbe.nested(p)==0,"unexpected method nesting");
            check(SchedulerTaskCpuProbe.depth(p)==0,"sample leaked");
            if (mode.equals("off")) {
                check(SchedulerTaskCpuProbe.calls(p)==0,"off had clock calls");
                check(SchedulerTaskCpuProbe.samples(p)==0,"off had clock samples");
            } else {
                long sampleCount=SchedulerTaskCpuProbe.samples(p);
                check(SchedulerTaskCpuProbe.calls(p)==20000,"lost method entries");
                check(sampleCount>450 && sampleCount<800,"incorrect 1/32 sampling");
                check(SchedulerTaskCpuProbe.cpuNanos(p)>=0,"negative cpu duration");
                check(SchedulerTaskCpuProbe.zeroDeltas(p)<=sampleCount,"invalid zero count");
            }
        }
        System.out.println("mode="+mode+" valid=true");
    }
}
