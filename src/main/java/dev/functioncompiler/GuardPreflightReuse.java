package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import java.util.concurrent.atomic.LongAdder;

/**
 * IR047: reuse the existing State's successful compound preflight only
 * across the exact same IR046 pure failed-guard boundary.
 * No stored references here; no global invalidation or mutation hooks.
 */
final class GuardPreflightReuse {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_GUARD_PREFLIGHT_REUSE"));
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static volatile boolean runtime = ENABLED;
    private static final LongAdder BOUNDARIES = new LongAdder();
    private static final LongAdder OBJECTIVES = new LongAdder();
    private static final LongAdder HOLDERS = new LongAdder();
    private static final LongAdder CRITERIA = new LongAdder();

    private GuardPreflightReuse() {}

    static boolean enabled() { return ENABLED && runtime; }

    static boolean benchmarkToggleAllowed() {
        return ENABLED && Boolean.parseBoolean(System.getenv("FC_TYPED_IR047_BENCHMARK"));
    }

    static int toggle(CommandSourceStack source, boolean on) {
        if (!benchmarkToggleAllowed()) return 0;
        runtime = on;
        source.sendSuccess(() -> Component.literal("IR047 preflight=" + on), false);
        return 1;
    }

    static void reused(int objectives, int holders) {
        if (DIAGNOSTICS) {
            BOUNDARIES.increment();
            OBJECTIVES.add(objectives);
            HOLDERS.add(holders);
            CRITERIA.increment();
        }
    }

    static String diagnostics() {
        return " ir047_boundaries=" + BOUNDARIES.sum()
                + " ir047_objective_lookups_avoided=" + OBJECTIVES.sum()
                + " ir047_holder_resolutions_avoided=" + HOLDERS.sum()
                + " ir047_criteria_checks_avoided=" + CRITERIA.sum();
    }
}
