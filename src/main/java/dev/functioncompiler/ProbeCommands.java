package dev.functioncompiler;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.ContextChain;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.resources.Identifier;
import net.minecraft.commands.Commands;
import net.minecraft.commands.execution.ChainModifiers;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.ExecutionControl;
import net.minecraft.commands.execution.Frame;
import net.minecraft.network.chat.Component;

final class ProbeCommands {
    private ProbeCommands() {
    }

    static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
        // IR-011: research-only same-JVM singleton response A/B control.
        // Both arms execute the exact same emitted instructions and
        // scoreboard writes; only one-result bookkeeping differs.
        if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SINGLETON_FEEDBACK"))
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SINGLETON_FEEDBACK_TOGGLE"))) {
            dispatcher.register(Commands.literal("fc_ir011_feedback")
                    .then(Commands.literal("on").executes(context ->
                            TypedScoreIR.toggleSingletonFeedback(context.getSource(), true)))
                    .then(Commands.literal("off").executes(context ->
                            TypedScoreIR.toggleSingletonFeedback(context.getSource(), false))));
        }
        // IR-010 research-only A/B switch. Both arms use identical compiled
        // bytecode in one native Minecraft JVM; only guarded source-value
        // reuse differs. Command does not exist in normal installations.
        if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SCORE_CACHE_TOGGLE"))
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SCORE_CACHE"))) {
            dispatcher.register(Commands.literal("fc_ir010_cache")
                    .then(Commands.literal("on").executes(context ->
                            TypedScoreIR.toggleCache(context.getSource(), true)))
                    .then(Commands.literal("off").executes(context ->
                            TypedScoreIR.toggleCache(context.getSource(), false))));
        }
        // CI-only scheduler-cost experiment. Never register these commands in
        // ordinary installations; the optional leaf increments a server-thread
        // local counter so the research harness can prove exact work completion.
        if (Boolean.parseBoolean(System.getenv("FC_SCHEDULER_RESEARCH"))) {
            dispatcher.register(Commands.literal("fc_research_noop").executes(context -> {
                ResearchCounter.EXECUTED++;
                return 1;
            }));
            dispatcher.register(Commands.literal("fc_research_count").executes(context -> {
                int count = ResearchCounter.EXECUTED;
                context.getSource().sendSuccess(
                        () -> Component.literal("FC_RESEARCH_COUNT " + count), false);
                return count;
            }));
        }

        // A test-only fire-and-forget call site matching tick function
        // invocation's empty result callback. This is NOT an alternative
        // public /function command; it keeps the ordinary /function callback
        // and tracer semantics on the original scheduler fallback.
        if (Boolean.parseBoolean(System.getenv("FC_DIRECT_SCHEDULER_HARNESS"))) {
            dispatcher.register(Commands.literal("fc_arch_call")
                    .then(Commands.argument("function", StringArgumentType.greedyString())
                            .executes(context -> researchQueueFunction(
                                    context.getSource(),
                                    StringArgumentType.getString(context, "function")
                            ))));
        }
        // IR-012 separate research-only call-site harness; queues with an
        // empty result callback like the tick scheduler, not public /function.
        if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIRECT_FUNCTION_HARNESS"))
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIRECT_FUNCTION"))) {
            dispatcher.register(Commands.literal("fc_ir012_call")
                    .then(Commands.argument("function", StringArgumentType.greedyString())
                            .executes(context -> researchQueueFunction(
                                    context.getSource(),
                                    StringArgumentType.getString(context, "function")
                            ))));
            dispatcher.register(Commands.literal("fc_ir012_direct")
                    .then(Commands.literal("on").executes(context ->
                            dev.functioncompiler.TypedScoreIRDirectScheduler.toggle(
                                    context.getSource(), true)))
                    .then(Commands.literal("off").executes(context ->
                            dev.functioncompiler.TypedScoreIRDirectScheduler.toggle(
                                    context.getSource(), false))));
        }

        // IR-017: bounded original-function native range-guard fixture,
        // separate from any public function invocation or production API.
        if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_RANGE_TEST_HARNESS"))) {
            dispatcher.register(Commands.literal("fc_ir017_call")
                    .then(Commands.argument("function", StringArgumentType.greedyString())
                            .executes(context -> researchQueueFunction(
                                    context.getSource(),
                                    StringArgumentType.getString(context, "function")))));
        }
        // IR-016: dedicated test-only, no-result function entrypoint.
        // It never exists in a normal mod installation.
        if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_MIXED_TEST_HARNESS"))) {
            dispatcher.register(Commands.literal("fc_ir016_call")
                    .then(Commands.argument("function", StringArgumentType.greedyString())
                            .executes(context -> researchQueueFunction(
                                    context.getSource(),
                                    StringArgumentType.getString(context, "function")))));
        }
        // IR-013 adversarial native test: queue a function from a synchronous
        // scoreboard callback. No command exists in normal installations.
        if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_REENTRANT_TEST_OBSERVER"))) {
            dispatcher.register(Commands.literal("fc_ir013_call")
                    .then(Commands.argument("function", StringArgumentType.greedyString())
                            .executes(context -> researchQueueFunction(
                                    context.getSource(),
                                    StringArgumentType.getString(context, "function")
                            ))));
            dispatcher.register(Commands.literal("fc_ir013_status").executes(context -> {
                context.getSource().sendSuccess(
                        () -> Component.literal("IR013" + ReentrantQueueProbe.diagnostics()), false);
                return 1;
            }));
        }

        dispatcher.register(Commands.literal("function_compiler_probe")
                .then(Commands.literal("status").executes(context -> ProbeStatus.status(context.getSource())))
                .then(Commands.literal("metrics").executes(context -> ProbeStatus.metrics(context.getSource())))
                .then(Commands.literal("acceptance").executes(context ->
                        CompilerAcceptanceAudit.report(context.getSource())))
                .then(Commands.literal("exec-census-start").executes(context ->
                        CompilerExecutionCensus.begin(context.getSource())))
                .then(Commands.literal("exec-census-stop").executes(context ->
                        CompilerExecutionCensus.finish(context.getSource())))
                .then(Commands.literal("cpu004-start").executes(context ->
                        CompilerPositionedCpuProbe.start(context.getSource())))
                .then(Commands.literal("cpu004-stop").executes(context ->
                        CompilerPositionedCpuProbe.stop(context.getSource())))
                .then(Commands.literal("cpu005-start").executes(context ->
                        CompilerQueueCpuProbe.start(context.getSource())))
                .then(Commands.literal("cpu005-stop").executes(context ->
                        CompilerQueueCpuProbe.stop(context.getSource())))
                .then(Commands.literal("macro006-start").executes(context ->
                        CompilerMacroLoadCpuProbe.start(context.getSource())))
                .then(Commands.literal("macro006-stop").executes(context ->
                        CompilerMacroLoadCpuProbe.stop(context.getSource())))
                .then(Commands.literal("ir008").executes(context ->
                        TypedScoreIR.report(context.getSource())))
                .then(Commands.literal("ir016")
                        .then(Commands.argument("function", StringArgumentType.greedyString())
                                .executes(context -> MixedFunctionIR.report(
                                        context.getSource(),
                                        StringArgumentType.getString(context, "function")))))
                .then(Commands.literal("reload").executes(context -> ProbeStatus.reloadConfig(context.getSource())))
                .then(Commands.literal("collect").executes(context -> ProbeStatus.collect(context.getSource())))
                .then(Commands.literal("stats")
                        .then(Commands.argument("function", StringArgumentType.greedyString())
                                .executes(context -> FunctionCompilerMod.stats(
                                        context.getSource(),
                                        StringArgumentType.getString(context, "function")
                                ))))
                .then(Commands.literal("measure")
                        .then(Commands.argument("function", StringArgumentType.greedyString())
                                .executes(context -> FunctionCompilerMod.measure(
                                        context.getSource(),
                                        StringArgumentType.getString(context, "function")
                                ))))
                .then(Commands.literal("run").executes(context -> FunctionCompilerMod.run(context.getSource()))));

        dispatcher.register(Commands.literal("functioncompiler")
                .then(Commands.literal("status").executes(context -> ProbeStatus.status(context.getSource())))
                .then(Commands.literal("metrics").executes(context -> ProbeStatus.metrics(context.getSource())))
                .then(Commands.literal("acceptance").executes(context ->
                        CompilerAcceptanceAudit.report(context.getSource())))
                .then(Commands.literal("exec-census-start").executes(context ->
                        CompilerExecutionCensus.begin(context.getSource())))
                .then(Commands.literal("exec-census-stop").executes(context ->
                        CompilerExecutionCensus.finish(context.getSource())))
                .then(Commands.literal("cpu004-start").executes(context ->
                        CompilerPositionedCpuProbe.start(context.getSource())))
                .then(Commands.literal("cpu004-stop").executes(context ->
                        CompilerPositionedCpuProbe.stop(context.getSource())))
                .then(Commands.literal("cpu005-start").executes(context ->
                        CompilerQueueCpuProbe.start(context.getSource())))
                .then(Commands.literal("cpu005-stop").executes(context ->
                        CompilerQueueCpuProbe.stop(context.getSource())))
                .then(Commands.literal("macro006-start").executes(context ->
                        CompilerMacroLoadCpuProbe.start(context.getSource())))
                .then(Commands.literal("macro006-stop").executes(context ->
                        CompilerMacroLoadCpuProbe.stop(context.getSource())))
                .then(Commands.literal("ir008").executes(context ->
                        TypedScoreIR.report(context.getSource())))
                .then(Commands.literal("ir016")
                        .then(Commands.argument("function", StringArgumentType.greedyString())
                                .executes(context -> MixedFunctionIR.report(
                                        context.getSource(),
                                        StringArgumentType.getString(context, "function")))))
                .then(Commands.literal("reload").executes(context -> ProbeStatus.reloadConfig(context.getSource())))
                .then(Commands.literal("collect").executes(context -> ProbeStatus.collect(context.getSource())))
                .then(Commands.literal("stats")
                        .then(Commands.argument("function", StringArgumentType.greedyString())
                                .executes(context -> FunctionCompilerMod.stats(
                                        context.getSource(),
                                        StringArgumentType.getString(context, "function")
                                )))));

        dispatcher.register(Commands.literal("fc_probe_leaf").executes(context -> {
            ProbeMetrics.moddedCommandExecuted();
            context.getSource().sendSuccess(
                    () -> Component.literal("FC_MODDED_LEAF executed"), false);
            return 7;
        }));

        dispatcher.register(Commands.literal("fc_probe_control_flow")
                .then(Commands.literal("step").executes(new CustomCommandExecutor.CommandAdapter<CommandSourceStack>() {
                    @Override
                    public void run(
                            CommandSourceStack source,
                            ContextChain<CommandSourceStack> chain,
                            ChainModifiers modifiers,
                            ExecutionControl<CommandSourceStack> control
                    ) {
                        ProbeMetrics.moddedControlFlowExecuted();
                        source.sendSuccess(() -> Component.literal("FC_CONTROL_FLOW step"), false);
                        source.callback().onResult(true, 7);
                    }
                }))
                .then(Commands.literal("discard").executes(new CustomCommandExecutor.CommandAdapter<CommandSourceStack>() {
                    @Override
                    public void run(
                            CommandSourceStack source,
                            ContextChain<CommandSourceStack> chain,
                            ChainModifiers modifiers,
                            ExecutionControl<CommandSourceStack> control
                    ) {
                        ProbeMetrics.moddedControlFlowExecuted();
                        source.sendSuccess(() -> Component.literal("FC_CONTROL_FLOW discard"), false);
                        control.currentFrame().discard();
                    }
                }))
                .then(Commands.literal("return_value")
                        .then(Commands.argument("value", IntegerArgumentType.integer())
                                .executes(new CustomCommandExecutor.CommandAdapter<CommandSourceStack>() {
                                    @Override
                                    public void run(
                                            CommandSourceStack source,
                                            ContextChain<CommandSourceStack> chain,
                                            ChainModifiers modifiers,
                                            ExecutionControl<CommandSourceStack> control
                                    ) {
                                        int value = IntegerArgumentType.getInteger(
                                                chain.getTopContext(), "value");
                                        ProbeMetrics.moddedControlFlowExecuted();
                                        source.callback().onSuccess(value);
                                        Frame frame = control.currentFrame();
                                        frame.returnSuccess(value);
                                        frame.discard();
                                    }
                                })))
                .then(Commands.literal("return_fail").executes(new CustomCommandExecutor.CommandAdapter<CommandSourceStack>() {
                    @Override
                    public void run(
                            CommandSourceStack source,
                            ContextChain<CommandSourceStack> chain,
                            ChainModifiers modifiers,
                            ExecutionControl<CommandSourceStack> control
                    ) {
                        ProbeMetrics.moddedControlFlowExecuted();
                        source.callback().onFailure();
                        Frame frame = control.currentFrame();
                        frame.returnFailure();
                        frame.discard();
                    }
                })));
    }
    /**
     * CI-only equal invocation path for C and D. Queue a no-callback function
     * through the same Minecraft ExecutionContext as the current command.
     * No default mod installation registers this command.
     */
    private static int researchQueueFunction(CommandSourceStack source, String name) {
        Identifier id = Identifier.tryParse(name);
        boolean previousArchFixture = id != null
                && (id.getNamespace().equals("fc_arch_fused")
                        || id.getNamespace().equals("fc_arch_direct"))
                && id.getPath().matches("score(_null)?_[0-9]+");
        boolean typedIrFixture = id != null
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIRECT_FUNCTION_HARNESS"))
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIRECT_FUNCTION"))
                && id.getNamespace().equals("fc_ir")
                && id.getPath().matches("ir012_[a-z0-9_]+");
        boolean reentrantFixture = id != null
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_REENTRANT_TEST_OBSERVER"))
                && id.getNamespace().equals("fc_ir")
                && id.getPath().matches("ir01[34]_[a-z0-9_]+");
        boolean mixedFixture = id != null
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_MIXED_TEST_HARNESS"))
                && id.getNamespace().equals("fc_ir")
                && id.getPath().matches("ir016_[a-z0-9_]+");
        boolean rangeFixture = id != null
                && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_RANGE_TEST_HARNESS"))
                && id.getNamespace().equals("fc_ir")
                && id.getPath().matches("ir017_[a-z0-9_]+");
        if (!previousArchFixture && !typedIrFixture && !reentrantFixture
                && !mixedFixture && !rangeFixture) {
            source.sendFailure(Component.literal("FC_ARCH invalid or disallowed function " + name));
            return 0;
        }
        ExecutionContext<CommandSourceStack> execution = ExecutionContextBridge.currentContext();
        if (execution == null) {
            source.sendFailure(Component.literal("FC_ARCH no execution context"));
            return 0;
        }
        var candidate = source.getServer().getFunctions().get(id);
        if (candidate.isEmpty()) {
            source.sendFailure(Component.literal("FC_ARCH missing function " + id));
            return 0;
        }
        try {
            InstantiatedFunction<CommandSourceStack> function =
                    candidate.get().instantiate(null, source.dispatcher());
            // Same no-result callback path for both C and D. This cannot
            // overwrite a parent callback or alter real /function behavior.
            ExecutionContext.queueInitialFunctionCall(
                    execution, function,
                    source.withSuppressedOutput().withCallback(CommandResultCallback.EMPTY),
                    CommandResultCallback.EMPTY);
        } catch (Exception failure) {
            source.sendFailure(Component.literal("FC_ARCH instantiation failed " + failure));
            return 0;
        }
        source.sendSuccess(() -> Component.literal("FC_ARCH_CALL queued " + id), false);
        return 1;
    }

    // A single Java thread executes the benchmark function and counter
    // queries; this is deliberately not a synchronized per-command increment.
    private static final class ResearchCounter {
        static int EXECUTED;
    }
}
