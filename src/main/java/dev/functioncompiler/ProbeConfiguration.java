package dev.functioncompiler;

public final class ProbeConfiguration {
    // Process environment variables are immutable for a running server. This
    // trace flag is consulted on every queue boundary and command cost debit;
    // avoid a System.getenv() hash-map lookup for every single command.
    private static final boolean TRACE_ENABLED = readBoolean("FC_RUNTIME_TRACE", false);
    private ProbeConfiguration() {
    }

    public static boolean wrapperEnabled() {
        return readBoolean("FC_WRAPPER_PROBE", CompilerConfig.isEnabled());
    }

    public static boolean traceEnabled() {
        return TRACE_ENABLED;
    }

    // Cached at process launch: attribution counters must never run in timed arms.
    private static final boolean SCHED_ARCH_COUNTERS_ENABLED =
            readBoolean("FC_SCHED_ARCH_COUNTERS", false);

    public static boolean schedulerArchitectureCountersEnabled() {
        return SCHED_ARCH_COUNTERS_ENABLED;
    }

    public static boolean scoreAddPrototypeEnabled() {
        return readBoolean(
                "FC_SCORE_ADD_PROTOTYPE",
                CompilerConfig.isScoreAddEnabled() || fusedRegionPrototypeEnabled()
        );
    }

    public static boolean scoreAddMetricsEnabled() {
        return readBoolean("FC_SCORE_ADD_METRICS", false);
    }

    public static boolean scoreAddTimingEnabled() {
        return readBoolean("FC_SCORE_ADD_TIMING", false);
    }

    public static boolean fusedRegionPrototypeEnabled() {
        return readBoolean("FC_FUSED_REGION_PROTOTYPE", CompilerConfig.isFusedRegions());
    }

    /** Optional research-only function namespace gate for fusion, not ScoreAdd. */
    public static boolean fusedRegionForFunction(net.minecraft.resources.Identifier id) {
        if (!fusedRegionPrototypeEnabled()) {
            return false;
        }
        String onlyNamespace = System.getenv("FC_FUSED_REGION_ONLY_NAMESPACE");
        return onlyNamespace == null || onlyNamespace.isBlank()
                || (id != null && onlyNamespace.equals(id.getNamespace()));
    }


    /**
     * Research-only opt-in. A nonblank namespace is MANDATORY: prevents this
     * restricted, unpromoted scheduling experiment affecting ordinary datapacks.
     */
    private static final boolean DIRECT_SCHEDULER_ENABLED =
            readBoolean("FC_DIRECT_SCHEDULER_PROTOTYPE", false);
    private static final String DIRECT_SCHEDULER_NAMESPACE =
            System.getenv("FC_DIRECT_SCHEDULER_ONLY_NAMESPACE");

    public static boolean directSchedulerPrototypeEnabled() {
        return DIRECT_SCHEDULER_ENABLED
                && DIRECT_SCHEDULER_NAMESPACE != null
                && !DIRECT_SCHEDULER_NAMESPACE.isBlank();
    }

    public static boolean directSchedulerForFunction(net.minecraft.resources.Identifier id) {
        return directSchedulerPrototypeEnabled()
                && id != null
                && DIRECT_SCHEDULER_NAMESPACE.equals(id.getNamespace());
    }

    private static final boolean DIRECT_SCHEDULER_DIAGNOSTICS =
            readBoolean("FC_DIRECT_SCHEDULER_DIAGNOSTICS", false);

    public static boolean directSchedulerDiagnosticsEnabled() {
        return DIRECT_SCHEDULER_DIAGNOSTICS;
    }

    public static boolean bytecodeRegionPrototypeEnabled() {
        return readBoolean("FC_BYTECODE_REGION_PROTOTYPE", CompilerConfig.isTieredBytecode());
    }

    public static boolean bytecodeCompileFailureEnabled() {
        return readBoolean("FC_BYTECODE_FORCE_COMPILE_FAILURE", false);
    }

    public static boolean functionTimingEnabled() {
        return readBoolean("FC_FUNCTION_TIMING", false);
    }

    public static boolean commandCallbackMetricsEnabled() {
        return readBoolean("FC_COMMAND_CALLBACK_METRICS", false);
    }

    public static boolean commandCallbackMetricsAllQueues() {
        return readBoolean("FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES", false);
    }

    public static boolean selectiveMacroArgumentsEnabled() {
        return readBoolean("FC_SELECTIVE_MACRO_ARGUMENTS", CompilerConfig.isSelectiveMacros());
    }

    public static boolean selectiveMacroArgumentsMetricsEnabled() {
        return readBoolean("FC_SELECTIVE_MACRO_ARGUMENTS_METRICS", false);
    }

    public static int bytecodeTieredThreshold() {
        String env = System.getenv("FC_BYTECODE_TIERED_THRESHOLD");
        if (env != null && !env.isBlank()) {
            return Integer.parseInt(env);
        }
        if (CompilerConfig.isTieredBytecode()) {
            return CompilerConfig.getTieredThreshold();
        }
        return 1;
    }

    public static boolean bytecodeColdPolicyEnabled() {
        String env = System.getenv("FC_BYTECODE_COLD_POLICY");
        if (env != null && !env.isBlank()) {
            return Boolean.parseBoolean(env);
        }
        return CompilerConfig.isTieredBytecode();
    }

    public static boolean bytecodeMacroEnabled() {
        return readBoolean("FC_BYTECODE_MACRO", true);
    }

    public static boolean isNamespaceExcluded(String namespace) {
        return CompilerConfig.isNamespaceExcluded(namespace);
    }

    private static boolean readBoolean(String envKey, boolean defaultValue) {
        String env = System.getenv(envKey);
        if (env != null && !env.isBlank()) {
            return Boolean.parseBoolean(env);
        }
        return defaultValue;
    }
}
