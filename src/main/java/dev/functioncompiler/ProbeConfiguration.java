package dev.functioncompiler;

public final class ProbeConfiguration {
    private ProbeConfiguration() {
    }

    /**
     * Environment variables are immutable after process startup in the normal
     * Java launcher. Cache their optional overrides once; do not cache
     * reloadable CompilerConfig fallback values. Null means no nonblank
     * override, retaining the existing blank / Boolean.parseBoolean behavior.
     */
    private static Boolean immutableBooleanOverride(String name) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? null : Boolean.parseBoolean(value);
    }

    private static final Boolean SCORE_ADD_OVERRIDE =
            immutableBooleanOverride("FC_SCORE_ADD_PROTOTYPE");
    private static final Boolean SCORE_ADD_TIMING_OVERRIDE =
            immutableBooleanOverride("FC_SCORE_ADD_TIMING");
    private static final Boolean SCORE_ADD_METRICS_OVERRIDE =
            immutableBooleanOverride("FC_SCORE_ADD_METRICS");

    public static boolean wrapperEnabled() {
        return readBoolean("FC_WRAPPER_PROBE", CompilerConfig.isEnabled());
    }

    public static boolean traceEnabled() {
        return readBoolean("FC_RUNTIME_TRACE", false);
    }

    public static boolean scoreAddPrototypeEnabled() {
        // Deliberately re-evaluate live config on every call without a fixed
        // environment override; function_compiler_probe reload must work.
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

    public static boolean fusedRegionPrototypeEnabled() {
        return readBoolean("FC_FUSED_REGION_PROTOTYPE", CompilerConfig.isFusedRegions());
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
