package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import java.util.concurrent.atomic.LongAdder;

/**
 * IR046: homogeneous two-range/set guard runs. Only exact symbolic slots
 * and their order are shared at compile time, never a live scoreboard object.
 * State owns all read facts and authorizes reuse only after a pure failure.
 */
final class GuardRunReuse {
    private static final boolean ENABLED = Boolean.parseBoolean(System.getenv("FC_TYPED_IR_GUARD_RUN_REUSE"));
    private static final boolean DIAGNOSTICS = Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static volatile boolean runtime = ENABLED;
    private static final LongAdder BOUNDARIES = new LongAdder(), PRESENT = new LongAdder(),
            ABSENT = new LongAdder(), INVALIDATIONS = new LongAdder(), TRACE = new LongAdder(),
            FORK = new LongAdder(), CALLBACK = new LongAdder();
    private GuardRunReuse() {}
    record Shape(TypedScoreIR.Slot first, TypedScoreIR.Slot second) {}

    static Shape shape(TypedScoreIR.Instruction instruction) {
        if (!ENABLED || !(instruction instanceof TypedScoreIR.Compound compound)
                || !compound.dataflow() || compound.predicates().size() != 2
                || !(compound.terminal() instanceof TypedScoreIR.Mutation mutation)
                || mutation.operation() != ScoreAddCommand.Operation.SET) return null;
        var first = compound.predicates().get(0);
        var second = compound.predicates().get(1);
        if (first.unless() || second.unless() || first.range() == null || second.range() == null) return null;
        var a = first.left().key();
        var b = second.left().key();
        var target = new TypedScoreIR.Slot(TypedScoreIR.slotName(mutation.holder(), mutation.holderSelf()), mutation.objective());
        // Fixed slot ordering: CompoundScoreIR interns first, second, then
        // identical target. No index remapping, alias inference or compare.
        if (a.equals(b) || !b.equals(target)) return null;
        return new Shape(a,b);
    }

    static boolean enabled() { return ENABLED && runtime; }
    static boolean benchmarkToggleAllowed() {
        return ENABLED && Boolean.parseBoolean(System.getenv("FC_TYPED_IR046_BENCHMARK"));
    }
    static int toggle(CommandSourceStack source, boolean on) {
        if (!benchmarkToggleAllowed()) return 0;
        runtime = on;
        source.sendSuccess(() -> Component.literal("IR046 reuse=" + on), false);
        return 1;
    }
    static void boundary() { if (DIAGNOSTICS) BOUNDARIES.increment(); }
    static void reused(boolean present) { if (DIAGNOSTICS) (present ? PRESENT : ABSENT).increment(); }
    static void invalidated() { if (DIAGNOSTICS) INVALIDATIONS.increment(); }
    static void rejected(boolean trace, boolean fork, boolean callback) {
        if (DIAGNOSTICS) {
            if (trace) TRACE.increment();
            if (fork) FORK.increment();
            if (callback) CALLBACK.increment();
        }
    }
    static String diagnostics() {
        return " ir046_boundaries=" + BOUNDARIES.sum() + " ir046_present_reuse=" + PRESENT.sum()
                + " ir046_absent_reuse=" + ABSENT.sum() + " ir046_invalidations=" + INVALIDATIONS.sum()
                + " ir046_trace_fallbacks=" + TRACE.sum() + " ir046_fork_fallbacks=" + FORK.sum()
                + " ir046_callback_fallbacks=" + CALLBACK.sum();
    }
}
