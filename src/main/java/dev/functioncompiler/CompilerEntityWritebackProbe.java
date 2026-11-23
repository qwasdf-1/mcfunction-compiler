package dev.functioncompiler;

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
 * Entity.load call nested in EntityDataAccessor.setData for the original
 * execute-store frontier coordinate paths.
 *
 * The outer execute-store callback establishes a short-lived, exact Marker
 * context. Only the same entity's synchronous Entity.load is timed. All
 * original operations still execute; this class is observation-only.
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
    private static final long[] STORE_COMPLETED = new long[3];
    private static final long[] LOAD_CALLS = new long[3];
    private static final long[] LOAD_COMPLETED = new long[3];
    private static final long[] SAMPLES = new long[3];
    private static final long[] CPU_NS = new long[3];
    private static final long[] INVALID = new long[3];
    private static final ThreadLocal<Integer> CURRENT_AXIS = new ThreadLocal<>();
    private static final ThreadLocal<Entity> CURRENT_ENTITY = new ThreadLocal<>();

    private CompilerEntityWritebackProbe() {
    }

    /**
     * Called at the exact DataAccessor.setData invocation in
     * ExecuteCommand.lambda$storeData$0. Returns -1 for every non-target.
     */
    public static int beginStore(
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
        CURRENT_AXIS.set(axis);
        CURRENT_ENTITY.set(entity);
        return axis;
    }

    /** Ends the outer store scope and restores the thread-local diagnostic state. */
    public static void endStore(int axis) {
        if (axis < 0) {
            return;
        }
        STORE_COMPLETED[axis]++;
        CURRENT_AXIS.remove();
        CURRENT_ENTITY.remove();
    }

    /**
     * Called only around Entity.load inside EntityDataAccessor.setData.
     * The identity guard ensures unrelated nested loads are not attributed.
     */
    public static long beginEntityLoad(Entity entity) {
        if (!CONFIGURED || !ACTIVE) {
            return -1L;
        }
        Integer axisValue = CURRENT_AXIS.get();
        if (axisValue == null || CURRENT_ENTITY.get() != entity) {
            return -1L;
        }
        int axis = axisValue;
        long ordinal = ++LOAD_CALLS[axis];
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

    public static void endEntityLoad(long started) {
        if (!CONFIGURED || !ACTIVE) {
            return;
        }
        Integer axisValue = CURRENT_AXIS.get();
        if (axisValue == null) {
            return;
        }
        int axis = axisValue;
        LOAD_COMPLETED[axis]++;
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
            STORE_COMPLETED[axis] = 0L;
            LOAD_CALLS[axis] = 0L;
            LOAD_COMPLETED[axis] = 0L;
            SAMPLES[axis] = 0L;
            CPU_NS[axis] = 0L;
            INVALID[axis] = 0L;
        }
        CURRENT_AXIS.remove();
        CURRENT_ENTITY.remove();
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
                            + "store_completed={} load_calls={} load_completed={} mounted={} "
                            + "other={} samples={} cpu_ns={} invalid={}",
                    AXES[axis], PATH_CALLS[axis], MARKER_CALLS[axis],
                    ELIGIBLE_CALLS[axis], STORE_COMPLETED[axis], LOAD_CALLS[axis],
                    LOAD_COMPLETED[axis], MOUNTED_CALLS[axis],
                    OTHER_ENTITY_CALLS[axis], SAMPLES[axis], CPU_NS[axis], INVALID[axis]);
        }
        FunctionCompilerMod.LOGGER.info("FC_IR031_END mode={} stride={}", MODE, STRIDE);
        source.sendSuccess(() -> net.minecraft.network.chat.Component.literal(
                "IR031 ended mode=" + MODE
                        + " loads=" + (LOAD_CALLS[0] + LOAD_CALLS[1]
                        + LOAD_CALLS[2])), false);
        return 1;
    }
}
