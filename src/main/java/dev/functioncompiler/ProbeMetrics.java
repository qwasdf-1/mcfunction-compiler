package dev.functioncompiler;

import net.minecraft.resources.Identifier;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

public final class ProbeMetrics {
    private static final AtomicLong WRAPPERS_CREATED = new AtomicLong();
    private static final AtomicLong WRAPPER_INSTANTIATIONS = new AtomicLong();
    private static final AtomicLong PROBE_FUNCTION_PARSE_COUNT = new AtomicLong();
    private static final AtomicLong SCORE_ADD_COMPILED = new AtomicLong();
    private static final AtomicLong SCORE_ADD_EXECUTED = new AtomicLong();
    private static final AtomicLong FUSED_REGIONS_COMPILED = new AtomicLong();
    private static final AtomicLong FUSED_REGIONS_EXECUTED = new AtomicLong();
    private static final ConcurrentMap<Identifier, AtomicLong> FUSED_REGIONS_BY_FUNCTION =
            new ConcurrentHashMap<>();
    private static final AtomicLong BYTECODE_REGIONS_COMPILED = new AtomicLong();
    private static final AtomicLong BYTECODE_REGIONS_COMPILE_FAILED = new AtomicLong();
    private static final AtomicLong BYTECODE_REGIONS_EXECUTED = new AtomicLong();
    private static final AtomicLong BYTECODE_CLASS_BYTES_GENERATED = new AtomicLong();
    private static final AtomicLong BYTECODE_TIERED_JIT_TRIGGERS = new AtomicLong();
    private static final AtomicLong MODDED_COMMAND_CALLS = new AtomicLong();
    private static final AtomicLong MODDED_CONTROL_FLOW_CALLS = new AtomicLong();
    private static final ConcurrentMap<Identifier, AtomicLong> SCORE_ADD_COMPILED_BY_FUNCTION =
            new ConcurrentHashMap<>();
    private static final ConcurrentMap<Identifier, AtomicLong> SCORE_ADD_EXECUTED_BY_FUNCTION =
            new ConcurrentHashMap<>();
    private static final ConcurrentMap<Identifier, AtomicLong> SCORE_ADD_TIMED_BY_FUNCTION =
            new ConcurrentHashMap<>();
    // DataStore modifiers compiled per function. Separate from the ScoreAdd
    // counter because that one also counts data commands and is incremented
    // again on every reload, so it cannot isolate this row's specialization.
    private static final ConcurrentMap<Identifier, AtomicLong> DATA_STORES_COMPILED_BY_FUNCTION =
            new ConcurrentHashMap<>();
    // Bossbar lines wrapped into StateMachineCommand per function, so the
    // ST-02 fixtures can prove their bossbar specialization with a counter a
    // vanilla fallback cannot produce.
    private static final ConcurrentMap<Identifier, AtomicLong> BOSSBARS_COMPILED_BY_FUNCTION =
            new ConcurrentHashMap<>();
    // Item commands (item replace/modify) wrapped into StateMachineCommand
    // per function, so the ST-06 fixture can prove its item-command
    // specialization with a counter a vanilla fallback cannot produce.
    private static final ConcurrentMap<Identifier, AtomicLong> ITEM_COMMANDS_COMPILED_BY_FUNCTION =
            new ConcurrentHashMap<>();
    // Per-namespace datapack coverage counters. A datapack normally owns one
    // namespace, so the namespace is the practical grouping for the load
    // report; see FunctionCoverageReport.
    private static final ConcurrentMap<String, AtomicLong> FUNCTIONS_BY_NAMESPACE =
            new ConcurrentHashMap<>();
    private static final ConcurrentMap<String, AtomicLong> COVERED_FUNCTIONS_BY_NAMESPACE =
            new ConcurrentHashMap<>();
    // Timed command callbacks run on the Minecraft server thread. These
    // test-only counters avoid adding atomic operations to the measured path.
    private static long SCORE_ADD_TIMED_CALLS;
    private static long SCORE_ADD_ELAPSED_NANOS;
    private static boolean EXECUTION_QUEUE_TIMER_ACTIVE;
    private static long EXECUTION_QUEUE_STARTED_NANOS;
    private static long EXECUTION_QUEUE_TIMED_CALLS;
    private static long EXECUTION_QUEUE_ELAPSED_NANOS;
    // The server executes function queues on its command thread. These
    // counters are opt-in because each leaf callback passes through Brigadier.
    private static boolean END_COMMAND_CALLBACK_SCOPE_REQUESTED;
    private static int COMMAND_CALLBACK_SCOPE_DEPTH;
    private static long GENERIC_LEAF_CALLBACKS;
    private static long OPTIMIZED_SCORE_ADD_LEAF_CALLBACKS;
    private static long SELECTIVE_MACRO_ARGUMENT_CALLS;
    private static final ConcurrentMap<String, AtomicLong> SELECTIVE_MACRO_UNSUPPORTED_PROVIDER_CLASSES = new ConcurrentHashMap<>();
    private static long SELECTIVE_MACRO_ARGUMENT_ATTEMPTS;
    private static long SELECTIVE_MACRO_UNSUPPORTED_PROVIDERS;
    private static long SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS;
    private static final ConcurrentMap<String, AtomicLong>
            SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS_MAP =
            new ConcurrentHashMap<>();    private static long SELECTIVE_MACRO_INVALID_STORAGE_SOURCES;
    private static long SELECTIVE_MACRO_MISSING_ENTITY_CUSTOM_DATA;
    private static long SELECTIVE_MACRO_MACRO_RESOLUTION_FALLBACKS;
    private static long SELECTIVE_MACRO_MISSING_SELECTED_KEYS;

    private ProbeMetrics() {
    }

    public static void wrapperCreated() {
        WRAPPERS_CREATED.incrementAndGet();
    }

    public static void wrapperInstantiated() {
        WRAPPER_INSTANTIATIONS.incrementAndGet();
    }

    public static long wrappersCreated() {
        return WRAPPERS_CREATED.get();
    }

    public static long wrapperInstantiations() {
        return WRAPPER_INSTANTIATIONS.get();
    }

    public static void probeFunctionParsed() {
        PROBE_FUNCTION_PARSE_COUNT.incrementAndGet();
    }

    public static long probeFunctionParseCount() {
        return PROBE_FUNCTION_PARSE_COUNT.get();
    }

    public static void scoreAddCompiled(Identifier functionId) {
        SCORE_ADD_COMPILED.incrementAndGet();
        AtomicLong perFunction = SCORE_ADD_COMPILED_BY_FUNCTION
                .computeIfAbsent(functionId, ignored -> new AtomicLong());
        if (perFunction.get() == 0L) {
            // First specialized command for this function: the function is covered.
            functionCovered(functionId.getNamespace());
        }
        perFunction.incrementAndGet();
    }

    /** Records a function built during datapack load, grouped by namespace. */
    public static void functionLoaded(String namespace) {
        FUNCTIONS_BY_NAMESPACE
                .computeIfAbsent(namespace, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    /** Records that at least one command in a function was specialized. */
    public static void functionCovered(String namespace) {
        COVERED_FUNCTIONS_BY_NAMESPACE
                .computeIfAbsent(namespace, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static void resetCoverageCounters() {
        FUNCTIONS_BY_NAMESPACE.clear();
        COVERED_FUNCTIONS_BY_NAMESPACE.clear();
    }

    public static java.util.Map<String, Long> functionsByNamespace() {
        java.util.Map<String, Long> snapshot = new java.util.LinkedHashMap<>();
        FUNCTIONS_BY_NAMESPACE.entrySet().stream()
                .sorted(java.util.Map.Entry.comparingByKey())
                .forEach(entry -> snapshot.put(entry.getKey(), entry.getValue().get()));
        return snapshot;
    }

    public static java.util.Map<String, Long> coveredFunctionsByNamespace() {
        java.util.Map<String, Long> snapshot = new java.util.LinkedHashMap<>();
        COVERED_FUNCTIONS_BY_NAMESPACE.entrySet().stream()
                .sorted(java.util.Map.Entry.comparingByKey())
                .forEach(entry -> snapshot.put(entry.getKey(), entry.getValue().get()));
        return snapshot;
    }

    public static long scoreAddsCompiled() {
        return SCORE_ADD_COMPILED.get();
    }

    public static long scoreAddsCompiled(Identifier functionId) {
        AtomicLong count = SCORE_ADD_COMPILED_BY_FUNCTION.get(functionId);
        return count == null ? 0 : count.get();
    }

    public static void dataStoreCompiled(Identifier functionId) {
        DATA_STORES_COMPILED_BY_FUNCTION
                .computeIfAbsent(functionId, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static long dataStoresCompiled(Identifier functionId) {
        AtomicLong count = DATA_STORES_COMPILED_BY_FUNCTION.get(functionId);
        return count == null ? 0 : count.get();
    }

    public static void bossbarCompiled(Identifier functionId) {
        BOSSBARS_COMPILED_BY_FUNCTION
                .computeIfAbsent(functionId, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static long bossbarsCompiled(Identifier functionId) {
        AtomicLong count = BOSSBARS_COMPILED_BY_FUNCTION.get(functionId);
        return count == null ? 0 : count.get();
    }

    public static void itemCommandCompiled(Identifier functionId) {
        ITEM_COMMANDS_COMPILED_BY_FUNCTION
                .computeIfAbsent(functionId, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static long itemCommandsCompiled(Identifier functionId) {
        AtomicLong count = ITEM_COMMANDS_COMPILED_BY_FUNCTION.get(functionId);
        return count == null ? 0 : count.get();
    }

    public static void scoreAddExecuted(Identifier functionId) {
        SCORE_ADD_EXECUTED.incrementAndGet();
        SCORE_ADD_EXECUTED_BY_FUNCTION
                .computeIfAbsent(functionId, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static long scoreAddsExecuted() {
        return SCORE_ADD_EXECUTED.get();
    }

    public static long scoreAddsExecuted(Identifier functionId) {
        AtomicLong count = SCORE_ADD_EXECUTED_BY_FUNCTION.get(functionId);
        return count == null ? 0 : count.get();
    }

    public static void fusedRegionsCompiled(int count) {
        FUSED_REGIONS_COMPILED.addAndGet(count);
    }

    public static void fusedRegionsCompiled(Identifier functionId, int count) {
        fusedRegionsCompiled(count);
        if (functionId != null) {
            FUSED_REGIONS_BY_FUNCTION.computeIfAbsent(functionId, ignored -> new AtomicLong())
                    .addAndGet(count);
        }
    }

    public static long fusedRegionsCompiled(Identifier functionId) {
        AtomicLong count = FUSED_REGIONS_BY_FUNCTION.get(functionId);
        return count == null ? 0 : count.get();
    }

    public static void fusedRegionExecuted() {
        FUSED_REGIONS_EXECUTED.incrementAndGet();
    }

    public static long fusedRegionsCompiled() {
        return FUSED_REGIONS_COMPILED.get();
    }

    public static long fusedRegionsExecuted() {
        return FUSED_REGIONS_EXECUTED.get();
    }

    public static void bytecodeRegionCompiled() {
        BYTECODE_REGIONS_COMPILED.incrementAndGet();
    }

    public static void bytecodeRegionCompileFailed() {
        BYTECODE_REGIONS_COMPILE_FAILED.incrementAndGet();
    }

    public static void bytecodeRegionExecuted() {
        BYTECODE_REGIONS_EXECUTED.incrementAndGet();
    }

    public static long bytecodeRegionsCompiled() {
        return BYTECODE_REGIONS_COMPILED.get();
    }

    public static long bytecodeRegionsCompileFailed() {
        return BYTECODE_REGIONS_COMPILE_FAILED.get();
    }

    public static long bytecodeRegionsExecuted() {
        return BYTECODE_REGIONS_EXECUTED.get();
    }

    public static void bytecodeClassBytesGenerated(long byteCount) {
        BYTECODE_CLASS_BYTES_GENERATED.addAndGet(byteCount);
    }

    public static long bytecodeClassBytesGenerated() {
        return BYTECODE_CLASS_BYTES_GENERATED.get();
    }

    public static void bytecodeTieredJitTriggered() {
        BYTECODE_TIERED_JIT_TRIGGERS.incrementAndGet();
    }

    public static long bytecodeTieredJitTriggers() {
        return BYTECODE_TIERED_JIT_TRIGGERS.get();
    }

    public static void moddedCommandExecuted() {
        MODDED_COMMAND_CALLS.incrementAndGet();
    }

    public static long moddedCommandCalls() {
        return MODDED_COMMAND_CALLS.get();
    }

    public static void moddedControlFlowExecuted() {
        MODDED_CONTROL_FLOW_CALLS.incrementAndGet();
    }

    public static long moddedControlFlowCalls() {
        return MODDED_CONTROL_FLOW_CALLS.get();
    }

    public static void scoreAddTimed(Identifier functionId, long elapsedNanos) {
        SCORE_ADD_TIMED_CALLS++;
        SCORE_ADD_ELAPSED_NANOS += elapsedNanos;
        SCORE_ADD_TIMED_BY_FUNCTION
                .computeIfAbsent(functionId, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static long scoreAddTimedCalls() {
        return SCORE_ADD_TIMED_CALLS;
    }

    public static long scoreAddElapsedNanos() {
        return SCORE_ADD_ELAPSED_NANOS;
    }

    public static long scoreAddTimedCalls(Identifier functionId) {
        AtomicLong count = SCORE_ADD_TIMED_BY_FUNCTION.get(functionId);
        return count == null ? 0 : count.get();
    }

    public static void beginExecutionQueueTiming() {
        EXECUTION_QUEUE_STARTED_NANOS = System.nanoTime();
        EXECUTION_QUEUE_TIMER_ACTIVE = true;
    }

    public static void endExecutionQueueTiming() {
        if (!EXECUTION_QUEUE_TIMER_ACTIVE) {
            return;
        }
        long elapsedNanos = System.nanoTime() - EXECUTION_QUEUE_STARTED_NANOS;
        EXECUTION_QUEUE_TIMER_ACTIVE = false;
        EXECUTION_QUEUE_ELAPSED_NANOS += elapsedNanos;
        EXECUTION_QUEUE_TIMED_CALLS++;
    }

    public static long executionQueueTimedCalls() {
        return EXECUTION_QUEUE_TIMED_CALLS;
    }

    public static long executionQueueElapsedNanos() {
        return EXECUTION_QUEUE_ELAPSED_NANOS;
    }

    public static void beginCommandCallbackScopeUntilQueueReturn() {
        beginCommandCallbackScope();
        END_COMMAND_CALLBACK_SCOPE_REQUESTED = true;
    }

    public static boolean consumeCommandCallbackScopeEndRequest() {
        boolean requested = END_COMMAND_CALLBACK_SCOPE_REQUESTED;
        END_COMMAND_CALLBACK_SCOPE_REQUESTED = false;
        return requested;
    }

    public static void beginCommandCallbackScope() {
        COMMAND_CALLBACK_SCOPE_DEPTH++;
    }

    public static void endCommandCallbackScope() {
        if (COMMAND_CALLBACK_SCOPE_DEPTH > 0) {
            COMMAND_CALLBACK_SCOPE_DEPTH--;
        }
    }

    public static boolean commandCallbackScopeActive() {
        return COMMAND_CALLBACK_SCOPE_DEPTH > 0;
    }

    public static void commandCallbackExecuted(boolean optimizedScoreAdd) {
        if (optimizedScoreAdd) {
            OPTIMIZED_SCORE_ADD_LEAF_CALLBACKS++;
        } else {
            GENERIC_LEAF_CALLBACKS++;
        }
    }

    public static long genericLeafCallbacks() {
        return GENERIC_LEAF_CALLBACKS;
    }

    public static long optimizedScoreAddLeafCallbacks() {
        return OPTIMIZED_SCORE_ADD_LEAF_CALLBACKS;
    }

    public static void selectiveMacroArgumentsUsed() {
        SELECTIVE_MACRO_ARGUMENT_CALLS++;
    }

    public static long selectiveMacroArgumentCalls() {
        return SELECTIVE_MACRO_ARGUMENT_CALLS;
    }

    public static void selectiveMacroArgumentsAttempted() {
        SELECTIVE_MACRO_ARGUMENT_ATTEMPTS++;
    }

    public static long selectiveMacroArgumentsAttemptedCount() {
        return SELECTIVE_MACRO_ARGUMENT_ATTEMPTS;
    }

    public static void selectiveMacroArgumentsUnsupportedProvider() {
        SELECTIVE_MACRO_UNSUPPORTED_PROVIDERS++;
    }

    public static void selectiveMacroArgumentsUnsupportedProvider(
            String providerClassName
    ) {
        if (providerClassName == null || providerClassName.isBlank()) {
            return;
        }
        SELECTIVE_MACRO_UNSUPPORTED_PROVIDERS++;
        SELECTIVE_MACRO_UNSUPPORTED_PROVIDER_CLASSES
                .computeIfAbsent(providerClassName, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static java.util.Map<String, Long> selectiveMacroUnsupportedProviderClasses() {
        java.util.TreeMap<String, Long> result = new java.util.TreeMap<>();
        for (var entry : SELECTIVE_MACRO_UNSUPPORTED_PROVIDER_CLASSES.entrySet()) {
            result.put(entry.getKey(), entry.getValue().get());
        }
        return result;
    }

    public static String selectiveMacroUnsupportedProviderClassSummary() {
        StringBuilder builder = new StringBuilder();
        for (var entry : SELECTIVE_MACRO_UNSUPPORTED_PROVIDER_CLASSES.entrySet()) {
            if (!builder.isEmpty()) {
                builder.append(',');
            }
            builder.append(entry.getKey()).append('=').append(entry.getValue().get());
        }
        return builder.substring(0, Math.min(builder.length(), 200));
    }

    public static long selectiveMacroArgumentsUnsupportedProviderCount() {
        return SELECTIVE_MACRO_UNSUPPORTED_PROVIDERS;
    }

    public static void selectiveMacroArgumentsUnsupportedEntityPath() {
        SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS++;
    }

    public static void selectiveMacroArgumentsUnsupportedEntityPath(
            String entityPath
    ) {
        String path = (entityPath == null || entityPath.isBlank())
                ? "unknown"
                : entityPath;
        SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS++;
        SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS_MAP
                .computeIfAbsent(path, ignored -> new AtomicLong())
                .incrementAndGet();
    }

    public static java.util.Map<String, Long> selectiveMacroUnsupportedEntityPaths() {
        java.util.TreeMap<String, Long> result = new java.util.TreeMap<>();
        for (var entry : SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS_MAP.entrySet()) {
            result.put(entry.getKey(), entry.getValue().get());
        }
        return result;
    }

    public static String selectiveMacroUnsupportedEntityPathSummary() {
        StringBuilder builder = new StringBuilder();
        for (var entry : SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS_MAP.entrySet()) {
            if (!builder.isEmpty()) {
                builder.append(',');
            }
            builder.append(entry.getKey()).append('=').append(entry.getValue().get());
        }
        return builder.substring(0, Math.min(builder.length(), 200));
    }

    public static long selectiveMacroArgumentsUnsupportedEntityPathCount() {
        return SELECTIVE_MACRO_UNSUPPORTED_ENTITY_PATHS;
    }
    public static void selectiveMacroArgumentsInvalidStorageSource() {
        SELECTIVE_MACRO_INVALID_STORAGE_SOURCES++;
    }

    public static long selectiveMacroArgumentsInvalidStorageSourceCount() {
        return SELECTIVE_MACRO_INVALID_STORAGE_SOURCES;
    }

    public static void selectiveMacroArgumentsMissingEntityCustomData() {
        SELECTIVE_MACRO_MISSING_ENTITY_CUSTOM_DATA++;
    }

    public static long selectiveMacroArgumentsMissingEntityCustomDataCount() {
        return SELECTIVE_MACRO_MISSING_ENTITY_CUSTOM_DATA;
    }

    public static void selectiveMacroArgumentsMacroResolutionFailed() {
        SELECTIVE_MACRO_MACRO_RESOLUTION_FALLBACKS++;
    }

    public static long selectiveMacroArgumentsMacroResolutionFailedCount() {
        return SELECTIVE_MACRO_MACRO_RESOLUTION_FALLBACKS;
    }

    public static void selectiveMacroArgumentsMissingSelectedKey() {
        SELECTIVE_MACRO_MISSING_SELECTED_KEYS++;
    }

    public static long selectiveMacroArgumentsMissingSelectedKeyCount() {
        return SELECTIVE_MACRO_MISSING_SELECTED_KEYS;
    }

}
