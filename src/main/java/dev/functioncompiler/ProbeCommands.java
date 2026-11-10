package dev.functioncompiler;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.ContextChain;
import net.minecraft.commands.CommandSourceStack;
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

        dispatcher.register(Commands.literal("function_compiler_probe")
                .then(Commands.literal("status").executes(context -> ProbeStatus.status(context.getSource())))
                .then(Commands.literal("metrics").executes(context -> ProbeStatus.metrics(context.getSource())))
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
    // A single Java thread executes the benchmark function and counter
    // queries; this is deliberately not a synchronized per-command increment.
    private static final class ResearchCounter {
        static int EXECUTED;
    }
}
