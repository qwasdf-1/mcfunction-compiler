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
    private ProbeCommands() {}
    static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
        CompilerFixtures.register(dispatcher);
        dispatcher.register(Commands.literal("function_compiler_probe")
                .then(Commands.literal("status").executes(context -> ProbeStatus.status(context.getSource())))
                .then(Commands.literal("metrics").executes(context -> ProbeStatus.metrics(context.getSource())))
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

    }
}
