package dev.functioncompiler;

public final class ProbeConfiguration {
    // Process environment variables are immutable for a running server. This
    // trace flag is consulted on every queue boundary and command cost debit;
    // avoid a System.getenv() hash-map lookup for every single command.
    private static final boolean TRACE_ENABLED = readBoolean("FC_RUNTIME_TRACE", false);
    // Env-only diagnostic flags (constant false default, no CompilerConfig
    // fallback), read at every ExecutionContext.runCommandQueue boundary and on
    // typed callback paths; cache them for the same reason as TRACE_ENABLED.
    private static final boolean COMMAND_CALLBACK_METRICS_ENABLED =
            readBoolean("FC_COMMAND_CALLBACK_METRICS", false);
    private static final boolean COMMAND_CALLBACK_METRICS_ALL_QUEUES =
            readBoolean("FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES", false);
    private ProbeConfiguration() {
    }

    /**
     * Environment variables are process immutable in the supported Java
     * launcher. Null means no nonblank override: recompute the fallback from
     * live CompilerConfig on every invocation so /reload still takes effect.
     * Parsing preserves the prior Boolean.parseBoolean/blank behavior.
     */
    private static Boolean envOverride(String name) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? null : Boolean.parseBoolean(value);
    }

    private static final Boolean SCORE_ADD_OVERRIDE = envOverride("FC_SCORE_ADD_PROTOTYPE");
    private static final Boolean SCORE_ADD_METRICS_OVERRIDE = envOverride("FC_SCORE_ADD_METRICS");
    private static final Boolean SCORE_ADD_TIMING_OVERRIDE = envOverride("FC_SCORE_ADD_TIMING");

    // Diagnostic-only same-JVM control. Never defaults to a real namespace.
    // This intentionally executes the old getenv path for an exactly named
    // benchmark namespace; no other function is affected.
    private static final String LEGACY_SCORE_ADD_NAMESPACE =
            System.getenv("FC_SCORE_ADD_LEGACY_NAMESPACE");

    public static boolean legacyScoreAddLookupForFunction(
            net.minecraft.resources.Identifier id) {
        return LEGACY_SCORE_ADD_NAMESPACE != null
                && !LEGACY_SCORE_ADD_NAMESPACE.isBlank()
                && id != null
                && LEGACY_SCORE_ADD_NAMESPACE.equals(id.getNamespace());
    }

    public static boolean scoreAddPrototypeEnabledLegacy() {
        return readBoolean("FC_SCORE_ADD_PROTOTYPE",
                CompilerConfig.isScoreAddEnabled() || fusedRegionPrototypeEnabled());
    }

    public static boolean scoreAddMetricsEnabledLegacy() {
        return readBoolean("FC_SCORE_ADD_METRICS", false);
    }

    public static boolean scoreAddTimingEnabledLegacy() {
        return readBoolean("FC_SCORE_ADD_TIMING", false);
    }

    public static boolean wrapperEnabled() {
        return readBoolean("FC_WRAPPER_PROBE", CompilerConfig.isEnabled() || TypedCompilerConfiguration.profileActive());
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
        // The fallback must remain dynamic; a null override never freezes
        // the reloadable score_add or fused_regions config gates.
        return SCORE_ADD_OVERRIDE != null
                ? SCORE_ADD_OVERRIDE.booleanValue()
                : CompilerConfig.isScoreAddEnabled() || fusedRegionPrototypeEnabled();
    }

    public static boolean scoreAddMetricsEnabled() {
        return SCORE_ADD_METRICS_OVERRIDE != null && SCORE_ADD_METRICS_OVERRIDE;
    }

    public static boolean scoreAddTimingEnabled() {
        return SCORE_ADD_TIMING_OVERRIDE != null && SCORE_ADD_TIMING_OVERRIDE;
    }

    // Entirely disabled in ordinary runs. These hard-coded research
    // namespaces must not become general compiler heuristics.
    private static final boolean SCORE_ADD_ATTRIBUTION_ENABLED =
            readBoolean("FC_SCORE_ADD_ATTRIBUTION", false);
    private static final boolean SCORE_ADD_PHASE_TIMERS_ENABLED =
            readBoolean("FC_SCORE_ADD_PHASE_TIMERS", false);
    private static final boolean SCORE_ADD_ATTR_DIAGNOSTICS_ENABLED =
            readBoolean("FC_SCORE_ADD_ATTR_DIAGNOSTICS", false);

    public static boolean scoreAddAttributionDiagnosticsEnabled() {
        return SCORE_ADD_ATTR_DIAGNOSTICS_ENABLED;
    }

    public static boolean scoreAddAttributionEnabled() {
        return SCORE_ADD_ATTRIBUTION_ENABLED;
    }

    public static boolean scoreAddPhaseTimersForFunction(net.minecraft.resources.Identifier id) {
        return SCORE_ADD_PHASE_TIMERS_ENABLED && id != null
                && "fc_attr_typed".equals(id.getNamespace());
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
        return COMMAND_CALLBACK_METRICS_ENABLED;
    }

    public static boolean commandCallbackMetricsAllQueues() {
        return COMMAND_CALLBACK_METRICS_ALL_QUEUES;
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

    // IR-030 is a research-only, exact-function opt-in. It is never enabled
    // by the ordinary compiler config and never broadens to an entire namespace.
    private static final boolean IR030_POS_GET_ENABLED =
            readBoolean("FC_IR030_POS_GET", false);
    private static final boolean IR030_POS_GET_VERIFY =
            readBoolean("FC_IR030_POS_GET_VERIFY", false);
    private static final String IR030_POS_GET_FUNCTIONS =
            System.getenv("FC_IR030_POS_GET_FUNCTIONS");

    public static boolean ir030PosGetEnabled() {
        return IR030_POS_GET_ENABLED;
    }

    public static boolean ir030PosGetVerify() {
        return IR030_POS_GET_VERIFY;
    }

    public static boolean ir030PosGetForFunction(net.minecraft.resources.Identifier id) {
        if (!IR030_POS_GET_ENABLED || id == null
                || IR030_POS_GET_FUNCTIONS == null
                || IR030_POS_GET_FUNCTIONS.isBlank()) {
            return false;
        }
        for (String entry : IR030_POS_GET_FUNCTIONS.split(",")) {
            if (id.toString().equals(entry.strip())) {
                return true;
            }
        }
        return false;
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
