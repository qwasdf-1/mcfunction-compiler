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

        dispatcher.register(Commands.literal("function_compiler_probe")
                .then(Commands.literal("status").executes(context -> ProbeStatus.status(context.getSource())))
                .then(Commands.literal("metrics").executes(context -> ProbeStatus.metrics(context.getSource())))
                .then(Commands.literal("acceptance").executes(context ->
                        CompilerAcceptanceAudit.report(context.getSource())))
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
        if (id == null
                || !(id.getNamespace().equals("fc_arch_fused")
                     || id.getNamespace().equals("fc_arch_direct"))
                || !id.getPath().matches("score(_null)?_[0-9]+")) {
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
