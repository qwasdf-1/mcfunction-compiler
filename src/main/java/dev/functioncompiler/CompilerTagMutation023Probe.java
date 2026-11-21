package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Marker;

import java.util.concurrent.atomic.AtomicLong;

/**
 * IR-023 RESEARCH ONLY. Strictly passive counters for original Blastback
 * marker tag changes, entity lifetime and visible-entity tracking. No
 * caching, iteration substitution, strong entity references, or predicates.
 *
 * Observation is INCOMPLETE for arbitrary entityTags().add/remove/clear
 * callers and arbitrary other-mod modifications of the backing Set. Load
 * events are separately counted, not misclassified as addTag() calls.
 */
public final class CompilerTagMutation023Probe {
    private static final String MODE = System.getenv("FC_CPU023_MODE");
    private static final String NAMESPACE = System.getenv("FC_CPU023_NAMESPACE");
    private static final boolean CONFIGURED = "erb".equals(NAMESPACE)
            && ("plain".equals(MODE) || "control".equals(MODE));
    private static final boolean COUNTING = "plain".equals(MODE);
    private static volatile boolean ACTIVE;

    private enum Metric {
        ADD_BLOCK_ATTEMPT, ADD_BLOCK_CHANGED, ADD_BLOCK_NOOP,
        ADD_VERIFIED_ATTEMPT, ADD_VERIFIED_CHANGED, ADD_VERIFIED_NOOP,
        REMOVE_BLOCK_ATTEMPT, REMOVE_BLOCK_CHANGED, REMOVE_BLOCK_NOOP,
        REMOVE_VERIFIED_ATTEMPT, REMOVE_VERIFIED_CHANGED, REMOVE_VERIFIED_NOOP,
        ELIGIBLE_ENTERED, ELIGIBLE_LEFT,
        MARKER_LOAD, LOAD_WITH_BLOCK, LOAD_ELIGIBLE,
        MARKER_MANAGER_ADDED, MANAGER_ADDED_WITH_BLOCK, MANAGER_ADDED_ELIGIBLE,
        MARKER_TRACKED, TRACKED_WITH_BLOCK, TRACKED_ELIGIBLE,
        MARKER_UNTRACKED, UNTRACKED_WITH_BLOCK, UNTRACKED_ELIGIBLE,
        MARKER_REMOVED, REMOVED_WITH_BLOCK, REMOVED_ELIGIBLE,
        REMOVED_UNLOADED_CHUNK, REMOVED_CHANGED_DIMENSION,
        REMOVED_KILLED, REMOVED_DISCARDED, REMOVED_OTHER,
        INVALID
    }
    private static final AtomicLong[] VALUES = new AtomicLong[Metric.values().length];
    static {
        for (int i = 0; i < VALUES.length; i++) VALUES[i] = new AtomicLong();
    }

    private CompilerTagMutation023Probe() {}

    private static void inc(Metric metric) { VALUES[metric.ordinal()].incrementAndGet(); }
    private static boolean enabledFor(Entity entity) {
        return ACTIVE && COUNTING && entity instanceof Marker;
    }
    private static boolean has(Entity entity, String tag) {
        return entity.entityTags().contains(tag);
    }
    private static boolean eligible(Entity entity) {
        return has(entity, "erb.block") && !has(entity, "erb.verified");
    }
    private static boolean watched(String tag) {
        return "erb.block".equals(tag) || "erb.verified".equals(tag);
    }
    /**
     * At native addTag/removeTag RETURN. The boolean is the actual Set
     * mutation result, NOT inferred from the command's reported success.
     * Eligibility transitions are inferred from the changed tag and
     * post-operation other-tag state, never by re-running a selector.
     */
    public static void tagReturn(Entity entity, String tag, boolean added, boolean changed) {
        if (!enabledFor(entity) || !watched(tag)) return;
        boolean block = "erb.block".equals(tag);
        if (added) {
            inc(block ? Metric.ADD_BLOCK_ATTEMPT : Metric.ADD_VERIFIED_ATTEMPT);
            if (changed) {
                inc(block ? Metric.ADD_BLOCK_CHANGED : Metric.ADD_VERIFIED_CHANGED);
                if (block && !has(entity, "erb.verified")) inc(Metric.ELIGIBLE_ENTERED);
                if (!block && has(entity, "erb.block")) inc(Metric.ELIGIBLE_LEFT);
            } else inc(block ? Metric.ADD_BLOCK_NOOP : Metric.ADD_VERIFIED_NOOP);
        } else {
            inc(block ? Metric.REMOVE_BLOCK_ATTEMPT : Metric.REMOVE_VERIFIED_ATTEMPT);
            if (changed) {
                inc(block ? Metric.REMOVE_BLOCK_CHANGED : Metric.REMOVE_VERIFIED_CHANGED);
                if (block && !has(entity, "erb.verified")) inc(Metric.ELIGIBLE_LEFT);
                if (!block && has(entity, "erb.block")) inc(Metric.ELIGIBLE_ENTERED);
            } else inc(block ? Metric.REMOVE_BLOCK_NOOP : Metric.REMOVE_VERIFIED_NOOP);
        }
    }

    public static void loaded(Entity entity) {
        if (!enabledFor(entity)) return;
        inc(Metric.MARKER_LOAD);
        if (has(entity, "erb.block")) inc(Metric.LOAD_WITH_BLOCK);
        if (eligible(entity)) inc(Metric.LOAD_ELIGIBLE);
    }

    public static void managerAdded(Entity entity, boolean accepted) {
        if (!accepted || !enabledFor(entity)) return;
        inc(Metric.MARKER_MANAGER_ADDED);
        if (has(entity, "erb.block")) inc(Metric.MANAGER_ADDED_WITH_BLOCK);
        if (eligible(entity)) inc(Metric.MANAGER_ADDED_ELIGIBLE);
    }

    public static void tracking(Entity entity, boolean start) {
        if (!enabledFor(entity)) return;
        inc(start ? Metric.MARKER_TRACKED : Metric.MARKER_UNTRACKED);
        if (has(entity, "erb.block"))
            inc(start ? Metric.TRACKED_WITH_BLOCK : Metric.UNTRACKED_WITH_BLOCK);
        if (eligible(entity))
            inc(start ? Metric.TRACKED_ELIGIBLE : Metric.UNTRACKED_ELIGIBLE);
    }

    public static void removing(Entity entity, Entity.RemovalReason reason) {
        if (!enabledFor(entity)) return;
        inc(Metric.MARKER_REMOVED);
        if (has(entity, "erb.block")) inc(Metric.REMOVED_WITH_BLOCK);
        if (eligible(entity)) inc(Metric.REMOVED_ELIGIBLE);
        switch (reason.name()) {
            case "UNLOADED_TO_CHUNK" -> inc(Metric.REMOVED_UNLOADED_CHUNK);
            case "CHANGED_DIMENSION" -> inc(Metric.REMOVED_CHANGED_DIMENSION);
            case "KILLED" -> inc(Metric.REMOVED_KILLED);
            case "DISCARDED" -> inc(Metric.REMOVED_DISCARDED);
            default -> inc(Metric.REMOVED_OTHER);
        }
    }

    public static int start(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(Component.literal(
                    "FC_CPU023 requires FC_CPU023_NAMESPACE=erb and MODE=control|plain"));
            return 0;
        }
        ACTIVE = false;
        for (AtomicLong counter : VALUES) counter.set(0);
        ACTIVE = true;
        source.sendSuccess(() -> Component.literal("FC_CPU023 started mode=" + MODE), false);
        return 1;
    }

    public static int stop(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_CPU023 was not active"));
            return 0;
        }
        ACTIVE = false;
        FunctionCompilerMod.LOGGER.info("FC_CPU023_BEGIN mode={}", MODE);
        for (Metric metric : Metric.values()) {
            FunctionCompilerMod.LOGGER.info("FC_CPU023_ROW kind={} count={}",
                    metric.name().toLowerCase(java.util.Locale.ROOT),
                    VALUES[metric.ordinal()].get());
        }
        FunctionCompilerMod.LOGGER.info("FC_CPU023_END mode={}", MODE);
        source.sendSuccess(() -> Component.literal("FC_CPU023 ended mode=" + MODE), false);
        return 1;
    }
}
