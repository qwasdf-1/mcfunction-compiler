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
    private static final Identifier DELEGATION_CONTROL = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "score_delegation_positive");
    private static final Identifier DELEGATION_SELECTOR = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "score_selector_declined");
    private static final Identifier DELEGATION_CLIENT_PACKET = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "state_machine_client_packet");
    // MO-02 fixtures. Their dedicated DataStore compile counters are the
    // falsifiable form of "the DataStore modifier specialized": each fixture
    // has exactly two `execute store ... storage` lines, so a parser that
    // declined them leaves the count at zero. Reloads may recompile the
    // function, so the assertion is a lower bound rather than an equality.
    private static final Identifier MO02_RESULT = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "mo02_store_result");
    private static final Identifier MO02_FAILURES = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "mo02_store_failures");
    // ST-02 fixtures. Their dedicated bossbar compile counters are the
    // falsifiable form of "the bossbar line specialized": each compiled wrap
    // event increments once (twice per store-chained line per generation,
    // the same doubling the DataStore counters show), so a parser that
    // declined the bossbar family leaves the count at zero. Bare bossbar
    // lines are not in the EXECUTE-stage parser list and stay vanilla, like
    // the other state-machine families outside tag/teleport/kill. Reloads
    // may recompile the function, so the assertion is a lower bound rather
    // than an equality.
    private static final Identifier ST02_OPS = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "st02_bossbar_ops");
    private static final Identifier ST02_VALUES = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "st02_bossbar_values");
    // The ST-06 modify-half fixture. Its dedicated item-command compile
    // counter is the falsifiable form of "the item modify line specialized":
    // each compiled wrap event increments once (twice per store-chained line
    // per generation, the same doubling the DataStore and bossbar counters
    // show), so a parser that declined the item family leaves the count at
    // zero. The fixture has one store-chained item modify line; bare item
    // lines are not in the EXECUTE-stage parser list and stay vanilla. The
    // `execute if items` conditions go through ItemPredicateParser, not this
    // counter. Reloads may recompile, so the assertion is a lower bound.
    private static final Identifier ST06_ITEM_MODIFY = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "st06_item_modify");

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
                + " score_add_compile_wall_ns=" + ProbeMetrics.scoreAddCompileWallNanos()
                + " fused_compile_wall_ns=" + ProbeMetrics.fusedCompileWallNanos()
                + " fused_regions_compiled=" + ProbeMetrics.fusedRegionsCompiled()
                + " fused_regions_executed=" + ProbeMetrics.fusedRegionsExecuted()
                + " arch_counters_enabled=" + ProbeConfiguration.schedulerArchitectureCountersEnabled()
                + " arch_nonempty_queue_visits=" + ProbeMetrics.archQueueBoundaryVisits()
                + " arch_quota_debits=" + ProbeMetrics.archQuotaDebits()
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
                // Delegation-contract fixtures: these functions contain only shapes
                // the specialized path must decline, so their per-function
                // specialization counters are the falsifiable form of the "stays
                // on the vanilla path" claim. A nonzero value means a command in
                // that function was specialized, which would need its own
                // semantic gate before the contract could be relied on.
                + " delegation_control_compiled=" + ProbeMetrics.scoreAddsCompiled(DELEGATION_CONTROL)
                + " delegation_control_executed=" + ProbeMetrics.scoreAddsExecuted(DELEGATION_CONTROL)
                + " delegation_selector_compiled=" + ProbeMetrics.scoreAddsCompiled(DELEGATION_SELECTOR)
                + " delegation_selector_executed=" + ProbeMetrics.scoreAddsExecuted(DELEGATION_SELECTOR)
                + " delegation_client_packet_compiled=" + ProbeMetrics.scoreAddsCompiled(DELEGATION_CLIENT_PACKET)
                + " delegation_client_packet_executed=" + ProbeMetrics.scoreAddsExecuted(DELEGATION_CLIENT_PACKET)
                + " data_store_compiled_mo02_result=" + ProbeMetrics.dataStoresCompiled(MO02_RESULT)
                + " data_store_compiled_mo02_failures=" + ProbeMetrics.dataStoresCompiled(MO02_FAILURES)
                + " bossbar_compiled_st02_bossbar_ops=" + ProbeMetrics.bossbarsCompiled(ST02_OPS)
                + " bossbar_compiled_st02_bossbar_values=" + ProbeMetrics.bossbarsCompiled(ST02_VALUES)
                + " item_command_compiled_st06_item_modify=" + ProbeMetrics.itemCommandsCompiled(ST06_ITEM_MODIFY)
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
                + ", unsupported_provider_classes=" + ProbeMetrics.selectiveMacroUnsupportedProviderClassSummary()                + ", invalid_storage_sources=" + ProbeMetrics.selectiveMacroArgumentsInvalidStorageSourceCount()
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
