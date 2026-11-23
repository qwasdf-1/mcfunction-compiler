package dev.functioncompiler;

import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.server.commands.data.DataAccessor;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Marker;
import dev.functioncompiler.mixin.EntityDataAccessorAccessor;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;

/**
 * IR-031 diagnostic only: sparse server-thread CPU clock around the exact
 * EntityDataAccessor.setData call inside ExecuteCommand.lambda$storeData$0.
 *
 * Counts only the three original vm:queue/append_here custom-data leaf paths
 * and requires an unmounted exact vanilla Marker. It does not alter the
 * accessor, NBT, result callback, command return, or Entity.load behavior.
 */
public final class CompilerEntityWritebackProbe {
    private static final String MODE = System.getenv("FC_IR031_MODE");
    private static final String NAMESPACE = System.getenv("FC_IR031_NAMESPACE");
    private static final int STRIDE = 16;
    private static final boolean CONFIGURED = "vm".equals(NAMESPACE)
            && ("plain".equals(MODE) || "empty".equals(MODE) || "timed".equals(MODE));
    private static final ThreadMXBean CLOCK = ManagementFactory.getThreadMXBean();
    private static volatile boolean ACTIVE;

    private static final String[] AXES = {"x", "y", "z"};
    private static final long[] PATH_CALLS = new long[3];
    private static final long[] MARKER_CALLS = new long[3];
    private static final long[] ELIGIBLE_CALLS = new long[3];
    private static final long[] MOUNTED_CALLS = new long[3];
    private static final long[] OTHER_ENTITY_CALLS = new long[3];
    private static final long[] COMPLETED_CALLS = new long[3];
    private static final long[] SAMPLES = new long[3];
    private static final long[] CPU_NS = new long[3];
    private static final long[] INVALID = new long[3];

    private CompilerEntityWritebackProbe() {
    }

    /**
     * Classify the exact outer-store setter invocation. Returns an axis only
     * for an unmounted exact Marker; all other calls remain native and untimed.
     */
    public static int classify(
            NbtPathArgument.NbtPath path,
            DataAccessor accessor
    ) {
        if (!CONFIGURED || !ACTIVE || path == null) {
            return -1;
        }
        int axis = switch (path.asString()) {
            case "data.frontier[-1].x" -> 0;
            case "data.frontier[-1].y" -> 1;
            case "data.frontier[-1].z" -> 2;
            default -> -1;
        };
        if (axis < 0) {
            return -1;
        }
        PATH_CALLS[axis]++;
        if (!(accessor instanceof EntityDataAccessorAccessor entityAccessor)) {
            OTHER_ENTITY_CALLS[axis]++;
            return -1;
        }
        Entity entity = entityAccessor.functionCompiler$getEntity();
        if (entity.getClass() != Marker.class) {
            OTHER_ENTITY_CALLS[axis]++;
            return -1;
        }
        MARKER_CALLS[axis]++;
        if (entity.getVehicle() != null) {
            MOUNTED_CALLS[axis]++;
            return -1;
        }
        ELIGIBLE_CALLS[axis]++;
        return axis;
    }

    /** -1 means no CPU interval opened for this callback. */
    public static long begin(int axis) {
        if (axis < 0) {
            return -1L;
        }
        long ordinal = ELIGIBLE_CALLS[axis];
        if ("plain".equals(MODE) || ordinal % STRIDE != 0) {
            return -1L;
        }
        if ("empty".equals(MODE)) {
            long before = now();
            observe(axis, now() - before);
            return -1L;
        }
        return now();
    }

    public static void end(int axis, long started) {
        if (axis < 0) {
            return;
        }
        COMPLETED_CALLS[axis]++;
        if (started >= 0L) {
            observe(axis, now() - started);
        }
    }

    private static long now() {
        return CLOCK.getCurrentThreadCpuTime();
    }

    private static void observe(int axis, long elapsed) {
        if (elapsed < 0L) {
            INVALID[axis]++;
        } else {
            SAMPLES[axis]++;
            CPU_NS[axis] += elapsed;
        }
    }

    private static void reset() {
        for (int axis = 0; axis < 3; axis++) {
            PATH_CALLS[axis] = 0L;
            MARKER_CALLS[axis] = 0L;
            ELIGIBLE_CALLS[axis] = 0L;
            MOUNTED_CALLS[axis] = 0L;
            OTHER_ENTITY_CALLS[axis] = 0L;
            COMPLETED_CALLS[axis] = 0L;
            SAMPLES[axis] = 0L;
            CPU_NS[axis] = 0L;
            INVALID[axis] = 0L;
        }
    }

    public static int start(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(net.minecraft.network.chat.Component.literal(
                    "IR031 requires FC_IR031_MODE and exact vm namespace"));
            return 0;
        }
        if (!"plain".equals(MODE)) {
            if (!CLOCK.isCurrentThreadCpuTimeSupported()) {
                source.sendFailure(net.minecraft.network.chat.Component.literal(
                        "IR031 Server-thread CPU clock unsupported"));
                return 0;
            }
            if (!CLOCK.isThreadCpuTimeEnabled()) {
                CLOCK.setThreadCpuTimeEnabled(true);
            }
            if (now() < 0L) {
                source.sendFailure(net.minecraft.network.chat.Component.literal(
                        "IR031 Server-thread CPU clock unavailable"));
                return 0;
            }
        }
        ACTIVE = false;
        reset();
        ACTIVE = true;
        source.sendSuccess(() -> net.minecraft.network.chat.Component.literal(
                "IR031 started mode=" + MODE), false);
        return 1;
    }

    public static int stop(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(net.minecraft.network.chat.Component.literal(
                    "IR031 was not active"));
            return 0;
        }
        ACTIVE = false;
        FunctionCompilerMod.LOGGER.info("FC_IR031_BEGIN mode={} stride={}", MODE, STRIDE);
        for (int axis = 0; axis < 3; axis++) {
            FunctionCompilerMod.LOGGER.info(
                    "FC_IR031_ROW axis={} path_calls={} marker_calls={} eligible={} "
                            + "completed={} mounted={} other={} samples={} cpu_ns={} invalid={}",
                    AXES[axis], PATH_CALLS[axis], MARKER_CALLS[axis],
                    ELIGIBLE_CALLS[axis], COMPLETED_CALLS[axis],
                    MOUNTED_CALLS[axis], OTHER_ENTITY_CALLS[axis],
                    SAMPLES[axis], CPU_NS[axis], INVALID[axis]);
        }
        FunctionCompilerMod.LOGGER.info("FC_IR031_END mode={} stride={}", MODE, STRIDE);
        source.sendSuccess(() -> net.minecraft.network.chat.Component.literal(
                "IR031 ended mode=" + MODE
                        + " eligible=" + (ELIGIBLE_CALLS[0] + ELIGIBLE_CALLS[1]
                        + ELIGIBLE_CALLS[2])), false);
        return 1;
    }
}
