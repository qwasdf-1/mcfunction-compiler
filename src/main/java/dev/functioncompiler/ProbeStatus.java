package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.MacroFunction;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.ServerFunctionManager;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.util.Optional;

final class ProbeStatus {
    private static final Identifier PROBE_FUNCTION = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "quota_three");
    private static final Identifier PROBE_TAG = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "wrapped");
    private static final Identifier LIFECYCLE_PROBE = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "probe");
    private static final Identifier LIFECYCLE_PROBE_V2 = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "probe_v2");
    private static final Identifier LIFECYCLE_TAG = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "probe");
    private static final Identifier LIFECYCLE_MACRO = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "macro_add");
    private static final Identifier LIFECYCLE_MACRO_PAIR = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "macro_pair");

    private ProbeStatus() {
    }

    static int collect(CommandSourceStack source) {
        System.gc();
        return status(source);
    }

    static int status(CommandSourceStack source) {
        ServerFunctionManager manager = source.getServer().getFunctions();
        Optional<CommandFunction<CommandSourceStack>> found = manager.get(PROBE_FUNCTION);
        if (found.isEmpty()) {
            source.sendFailure(Component.literal("FC_PROBE missing function " + PROBE_FUNCTION));
            return 0;
        }

        CommandFunction<CommandSourceStack> function = found.get();
        boolean wrapped = function instanceof ProbeFunctionWrapper<?>;
        boolean tagHasSameInstance = manager.getTag(PROBE_TAG).stream().anyMatch(tagged -> tagged == function);
        boolean delegatesToOriginalInstantiation;
        boolean originalFallbackRetained;
        try {
            delegatesToOriginalInstantiation = delegatesToOriginalInstantiation(function, manager);
            originalFallbackRetained = originalFallbackRetained(function, manager);
        } catch (Exception exception) {
            source.sendFailure(Component.literal("FC_PROBE delegation check failed: " + exception));
            return 0;
        }

        String message = "FC_PROBE present=true wrapped=" + wrapped
                + " tag_same_instance=" + tagHasSameInstance
                + " delegates_original=" + delegatesToOriginalInstantiation
                + " original_fallback_retained=" + originalFallbackRetained
                + " lifecycle_probe_wrapped=" + isWrapped(manager, LIFECYCLE_PROBE)
                + " lifecycle_probe_v2_wrapped=" + isWrapped(manager, LIFECYCLE_PROBE_V2)
                + " lifecycle_tag_has_probe=" + tagContains(manager, LIFECYCLE_TAG, LIFECYCLE_PROBE)
                + " lifecycle_tag_same_probe_instance=" + tagContainsSameInstance(
                        manager, LIFECYCLE_TAG, LIFECYCLE_PROBE)
                + " lifecycle_tag_has_probe_v2=" + tagContains(
                        manager, LIFECYCLE_TAG, LIFECYCLE_PROBE_V2)
                + " lifecycle_tag_same_probe_v2_instance=" + tagContainsSameInstance(
                        manager, LIFECYCLE_TAG, LIFECYCLE_PROBE_V2)
                + " lifecycle_macro_is_macro=" + isMacro(manager, LIFECYCLE_MACRO)
                + " lifecycle_macro_wrapped=" + isWrapped(manager, LIFECYCLE_MACRO)
                + " wrapper_enabled=" + ProbeConfiguration.wrapperEnabled()
                + " score_add_prototype_enabled=" + ProbeConfiguration.scoreAddPrototypeEnabled()
                + " score_add_metrics_enabled=" + ProbeConfiguration.scoreAddMetricsEnabled()
                + " score_add_timing_enabled=" + ProbeConfiguration.scoreAddTimingEnabled()
                + " fused_region_prototype_enabled=" + ProbeConfiguration.fusedRegionPrototypeEnabled()
                + " bytecode_region_prototype_enabled=" + ProbeConfiguration.bytecodeRegionPrototypeEnabled()
                + " bytecode_compile_failure_forced=" + ProbeConfiguration.bytecodeCompileFailureEnabled()
                + " fused_regions_compiled=" + ProbeMetrics.fusedRegionsCompiled()
                + " fused_regions_executed=" + ProbeMetrics.fusedRegionsExecuted()
                + " bytecode_regions_compiled=" + ProbeMetrics.bytecodeRegionsCompiled()
                + " bytecode_regions_compile_failed=" + ProbeMetrics.bytecodeRegionsCompileFailed()
                + " bytecode_regions_executed=" + ProbeMetrics.bytecodeRegionsExecuted()
                + " bytecode_tiered_jit_triggers=" + ProbeMetrics.bytecodeTieredJitTriggers()
                + " bytecode_generated_classes_live=" + BytecodeRegionPrototype.liveGeneratedClassCount()
                + " bytecode_classloader_identity=" + BytecodeRegionPrototype.generatedClassLoaderIdentity()
                + " bytecode_class_bytes_emitted=" + ProbeMetrics.bytecodeClassBytesGenerated()
                + " modded_leaf_calls=" + ProbeMetrics.moddedCommandCalls()
                + " modded_control_flow_calls=" + ProbeMetrics.moddedControlFlowCalls()
                + " metaspace_bytes_used=" + memoryPoolUsed("Metaspace")
                + " score_add_compiled=" + ProbeMetrics.scoreAddsCompiled()
                + " score_add_compiled_lifecycle_probe=" + ProbeMetrics.scoreAddsCompiled(LIFECYCLE_PROBE)
                + " score_add_compiled_lifecycle_macro_add=" + ProbeMetrics.scoreAddsCompiled(LIFECYCLE_MACRO)
                + " score_add_compiled_lifecycle_macro_pair=" + ProbeMetrics.scoreAddsCompiled(LIFECYCLE_MACRO_PAIR)
                + " score_add_executed=" + ProbeMetrics.scoreAddsExecuted()
                + " score_add_executed_lifecycle_macro_add=" + ProbeMetrics.scoreAddsExecuted(LIFECYCLE_MACRO)
                + " score_add_executed_lifecycle_macro_pair=" + ProbeMetrics.scoreAddsExecuted(LIFECYCLE_MACRO_PAIR)
                + " score_add_timed_calls=" + ProbeMetrics.scoreAddTimedCalls()
                + " score_add_timed_lifecycle_macro_add=" + ProbeMetrics.scoreAddTimedCalls(LIFECYCLE_MACRO)
                + " score_add_timed_lifecycle_macro_pair=" + ProbeMetrics.scoreAddTimedCalls(LIFECYCLE_MACRO_PAIR)
                + " score_add_elapsed_nanos=" + ProbeMetrics.scoreAddElapsedNanos()
                + " function_timing_enabled=" + ProbeConfiguration.functionTimingEnabled()
                + " function_timed_calls=" + ProbeMetrics.executionQueueTimedCalls()
                + " function_elapsed_nanos=" + ProbeMetrics.executionQueueElapsedNanos()
                + " command_callback_metrics_enabled="
                + ProbeConfiguration.commandCallbackMetricsEnabled()
                + " command_callback_metrics_all_queues="
                + ProbeConfiguration.commandCallbackMetricsAllQueues()
                + " selective_macro_arguments_enabled="
                + ProbeConfiguration.selectiveMacroArgumentsEnabled()
                + " selective_macro_arguments_metrics_enabled="
                + ProbeConfiguration.selectiveMacroArgumentsMetricsEnabled()
                + " selective_macro_arguments_used="
                + ProbeMetrics.selectiveMacroArgumentCalls()
                + " selective_macro_argument_attempts="
                + ProbeMetrics.selectiveMacroArgumentsAttemptedCount()
                + " selective_macro_unsupported_providers="
                + ProbeMetrics.selectiveMacroArgumentsUnsupportedProviderCount()
                + " selective_macro_unsupported_entity_paths="
                + ProbeMetrics.selectiveMacroArgumentsUnsupportedEntityPathCount()
                + " selective_macro_invalid_storage_sources="
                + ProbeMetrics.selectiveMacroArgumentsInvalidStorageSourceCount()
                + " selective_macro_missing_entity_custom_data="
                + ProbeMetrics.selectiveMacroArgumentsMissingEntityCustomDataCount()
                + " selective_macro_macro_resolution_fallbacks="
                + ProbeMetrics.selectiveMacroArgumentsMacroResolutionFailedCount()
                + " selective_macro_missing_selected_keys="
                + ProbeMetrics.selectiveMacroArgumentsMissingSelectedKeyCount()
                + " selective_macro_unsupported_provider_classes="
                + ProbeMetrics.selectiveMacroUnsupportedProviderClassSummary()
                + " generic_leaf_callbacks=" + ProbeMetrics.genericLeafCallbacks()
                + " optimized_score_add_leaf_callbacks="
                + ProbeMetrics.optimizedScoreAddLeafCallbacks()
                + " wrappers_created=" + ProbeMetrics.wrappersCreated()
                + " wrapper_instantiations=" + ProbeMetrics.wrapperInstantiations()
                + " probe_function_parses=" + ProbeMetrics.probeFunctionParseCount();
        source.sendSuccess(() -> Component.literal(message), false);
        FunctionCompilerMod.LOGGER.info(message);
        boolean expectedDelegate = !ProbeConfiguration.fusedRegionPrototypeEnabled()
                && (!ProbeConfiguration.bytecodeRegionPrototypeEnabled()
                || ProbeConfiguration.bytecodeCompileFailureEnabled());
        return wrapped && tagHasSameInstance && originalFallbackRetained
                && delegatesToOriginalInstantiation == expectedDelegate ? 1 : 0;
    }

    private static long memoryPoolUsed(String poolNameFragment) {
        return ManagementFactory.getMemoryPoolMXBeans().stream()
                .filter(pool -> pool.getName().contains(poolNameFragment))
                .map(MemoryPoolMXBean::getUsage)
                .filter(usage -> usage != null)
                .mapToLong(usage -> usage.getUsed())
                .sum();
    }

    private static boolean isWrapped(ServerFunctionManager manager, Identifier id) {
        return manager.get(id).map(function -> function instanceof ProbeFunctionWrapper<?>).orElse(false);
    }

    private static boolean tagContains(ServerFunctionManager manager, Identifier tag, Identifier id) {
        return manager.getTag(tag).stream().anyMatch(function -> function.id().equals(id));
    }

    private static boolean tagContainsSameInstance(
            ServerFunctionManager manager,
            Identifier tag,
            Identifier id
    ) {
        Optional<CommandFunction<CommandSourceStack>> found = manager.get(id);
        return found.isPresent()
                && manager.getTag(tag).stream().anyMatch(function -> function == found.get());
    }

    private static boolean isMacro(ServerFunctionManager manager, Identifier id) {
        return manager.get(id).map(function -> {
            if (function instanceof ProbeFunctionWrapper<?> wrapper) {
                return wrapper.delegate() instanceof MacroFunction<?>;
            }
            return function instanceof MacroFunction<?>;
        }).orElse(false);
    }

    @SuppressWarnings("unchecked")
    private static boolean delegatesToOriginalInstantiation(
            CommandFunction<CommandSourceStack> function,
            ServerFunctionManager manager
    ) throws Exception {
        if (function instanceof ProbeFunctionWrapper<?> wrapper) {
            ProbeFunctionWrapper<CommandSourceStack> typed = (ProbeFunctionWrapper<CommandSourceStack>) wrapper;
            return typed.instantiate(null, manager.getDispatcher()) == typed.delegate();
        }
        return function.instantiate(null, manager.getDispatcher()) == function;
    }

    @SuppressWarnings("unchecked")
    private static boolean originalFallbackRetained(
            CommandFunction<CommandSourceStack> function,
            ServerFunctionManager manager
    ) throws Exception {
        if (function instanceof ProbeFunctionWrapper<?> wrapper) {
            ProbeFunctionWrapper<CommandSourceStack> typed =
                    (ProbeFunctionWrapper<CommandSourceStack>) wrapper;
            return typed.originalFallbackRetained(manager.getDispatcher());
        }
        return function.instantiate(null, manager.getDispatcher()) == function;
    }

    static int metrics(CommandSourceStack source) {
        String message = "Function Compiler v1.0 Production Metrics:\n"
                + "  • Fused Regions: compiled=" + ProbeMetrics.fusedRegionsCompiled()
                + ", executed=" + ProbeMetrics.fusedRegionsExecuted() + "\n"
                + "  • Bytecode Regions: compiled=" + ProbeMetrics.bytecodeRegionsCompiled()
                + ", executed=" + ProbeMetrics.bytecodeRegionsExecuted()
                + ", live_classes=" + BytecodeRegionPrototype.liveGeneratedClassCount() + "\n"
                + "  • Tiered JIT Triggers: " + ProbeMetrics.bytecodeTieredJitTriggers() + "\n"
                + "  • Selective Macro Hits: " + ProbeMetrics.selectiveMacroArgumentCalls() + "\n"
                + "  • Selective Macro Diagnostics: attempts=" + ProbeMetrics.selectiveMacroArgumentsAttemptedCount()
                + ", unsupported_providers=" + ProbeMetrics.selectiveMacroArgumentsUnsupportedProviderCount()
                + ", unsupported_provider_classes="
                + ProbeMetrics.selectiveMacroUnsupportedProviderClassSummary()
                + ", unsupported_entity_paths=" + ProbeMetrics.selectiveMacroArgumentsUnsupportedEntityPathCount()
                + ", invalid_storage_sources=" + ProbeMetrics.selectiveMacroArgumentsInvalidStorageSourceCount()
                + ", missing_entity_custom_data=" + ProbeMetrics.selectiveMacroArgumentsMissingEntityCustomDataCount()
                + ", macro_resolution_fallbacks=" + ProbeMetrics.selectiveMacroArgumentsMacroResolutionFailedCount()
                + ", missing_selected_keys=" + ProbeMetrics.selectiveMacroArgumentsMissingSelectedKeyCount() + "\n"
                + "  • Scoreboard Operations: compiled=" + ProbeMetrics.scoreAddsCompiled()
                + ", executed=" + ProbeMetrics.scoreAddsExecuted();
        source.sendSuccess(() -> Component.literal(message), false);
        return 1;
    }

    static int reloadConfig(CommandSourceStack source) {
        CompilerConfig.load();
        source.sendSuccess(() -> Component.literal(
                "Function Compiler configuration reloaded from config/function-compiler.json"), true);
        return 1;
    }
}
