package dev.functioncompiler;

/**
 * Research-only, event-scoped synthetic ExecuteCommand result-callback site
 * census. Reuses the original selected 1/32 parent ExecuteCommand method and
 * the existing RESULT CPU clock: NO extra ThreadMXBean clock reads.
 *
 * The known 26.3 callback construction sites are ScoreAccess.set, bossbar
 * value/max setters, NBT DataAccessor.setData, and function-condition list
 * collection. Each synthetic callback receives a probe at method HEAD and
 * leaves original game/scoreboard state-changing behavior untouched.
 */
public final class SchedulerResultSiteTrace {
    public enum Site {
        SCORE_STORE, BOSSBAR_STORE, DATA_STORE, FUNCTION_CONDITION,
        NO_SITE, MULTIPLE
    }

    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_SCHED_RESULT_SITE_TRACE"));
    private static final long[] CALLS = new long[Site.values().length];
    private static final long[] RAW_CPU_NS = new long[Site.values().length];
    private static long observedCallbacks;
    private static long observedCpuNs;
    private static long ownerThreadId = -1;
    private static boolean active;
    private static Site observedSite;
    private static int siteHits;
    private static long unexpectedNestedScopes;

    private SchedulerResultSiteTrace() {}

    public static boolean enabled() { return ENABLED; }

    private static void assertThread() {
        if (!"Server thread".equals(Thread.currentThread().getName())) {
            throw new IllegalStateException("Site census invoked outside Server thread");
        }
        long tid = Thread.currentThread().threadId();
        if (ownerThreadId == -1) ownerThreadId = tid;
        else if (ownerThreadId != tid) {
            throw new IllegalStateException("Site census changed Server thread");
        }
    }

    /** Called just BEFORE the prior RESULT CPU interval begins. */
    public static void openSelectedScope() {
        if (!ENABLED
                || !SchedulerTaskCpuProbe.activeSampled(SchedulerTaskCpuProbe.Path.EXECUTE)) {
            return;
        }
        assertThread();
        if (active) {
            unexpectedNestedScopes++;
            throw new IllegalStateException("Nested selected ResultConsumer scope");
        }
        active = true;
        observedSite = null;
        siteHits = 0;
    }

    /** Called by only the four exact 26.3 synthetic callback method HEADs. */
    public static void observeSite(Site site) {
        if (!ENABLED || !active) return;
        if (site == Site.NO_SITE || site == Site.MULTIPLE) {
            throw new IllegalArgumentException("Site probes must use concrete callback labels");
        }
        assertThread();
        siteHits++;
        if (siteHits == 1) observedSite = site;
        else observedSite = Site.MULTIPLE;
    }

    /**
     * Called only AFTER the original inclusive RESULT CPU interval closes.
     * Records original elapsed nanos without any extra CPU-clock reads.
     */
    public static void closeSelectedScope(long token, long rawNs) {
        if (!ENABLED || !active) return;
        assertThread();
        if (token == SchedulerPhaseCpuProbe.SKIP
                || token == SchedulerPhaseCpuProbe.NESTED) {
            throw new IllegalStateException("Site scope had no selected parent clock token");
        }
        Site result = siteHits == 0 ? Site.NO_SITE : observedSite;
        if (result == null) throw new IllegalStateException("Missing callback site");
        CALLS[result.ordinal()]++;
        observedCallbacks++;
        if (rawNs >= 0) {
            RAW_CPU_NS[result.ordinal()] = Math.addExact(
                    RAW_CPU_NS[result.ordinal()], rawNs);
            observedCpuNs = Math.addExact(observedCpuNs, rawNs);
        }
        active = false;
        observedSite = null;
        siteHits = 0;
    }

    public static String summary() {
        StringBuilder b = new StringBuilder("FC_SCHED_SITES");
        b.append(" enabled=").append(ENABLED);
        b.append(" mode=").append(SchedulerPhaseCpuProbe.modeName());
        b.append(" thread=").append(ownerThreadId);
        b.append(" callbacks=").append(observedCallbacks);
        b.append(" raw_cpu_ns=").append(observedCpuNs);
        b.append(" nested=").append(unexpectedNestedScopes);
        b.append(" sites=");
        for (Site site : Site.values()) {
            if (site != Site.SCORE_STORE) b.append(';');
            b.append(site.name()).append('|').append(CALLS[site.ordinal()])
                    .append('|').append(RAW_CPU_NS[site.ordinal()]);
        }
        return b.toString();
    }
}
