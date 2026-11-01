package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.ExecutionContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

final class InlinedFunctionCommand implements FusableCommand {
    private final Command<CommandSourceStack> originalCommand;
    private final PlainTextFunction<CommandSourceStack> targetFunction;
    private final Identifier parentFunctionId;

    InlinedFunctionCommand(
            Command<CommandSourceStack> originalCommand,
            PlainTextFunction<CommandSourceStack> targetFunction,
            Identifier parentFunctionId
    ) {
        this.originalCommand = originalCommand;
        this.targetFunction = targetFunction;
        this.parentFunctionId = parentFunctionId;
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context) throws CommandSyntaxException {
        if (ProbeConfiguration.scoreAddTimingEnabled()) {
            long started = System.nanoTime();
            try {
                return runUntimed(context);
            } finally {
                ProbeMetrics.scoreAddTimed(parentFunctionId, System.nanoTime() - started);
            }
        }
        return runUntimed(context);
    }

    private int runUntimed(CommandContext<CommandSourceStack> context)
            throws CommandSyntaxException {
        ExecutionContext<CommandSourceStack> execContext = ExecutionContextBridge.currentContext();
        if (execContext == null || execContext.tracer() != null
                || (!ProbeConfiguration.scoreAddPrototypeEnabled() && !ProbeConfiguration.fusedRegionPrototypeEnabled())) {
            return originalCommand.run(context);
        }

        if (!canDebit(execContext)) {
            return 0;
        }

        CommandSourceStack source = context.getSource();
        int totalResult = 0;
        for (UnboundEntryAction<CommandSourceStack> entry : targetFunction.entries()) {
            if (!canDebit(execContext)) {
                break;
            }
            totalResult += executeEntry(entry, source, execContext);
        }

        source.sendSuccess(
                () -> Component.translatable(
                        "commands.function.scheduled.single",
                        Component.translationArg(targetFunction.id())
                ),
                true
        );

        ProbeMetrics.moddedCommandExecuted();
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(parentFunctionId);
        }
        return totalResult > 0 ? totalResult : 1;
    }

    private int executeEntry(
            UnboundEntryAction<CommandSourceStack> entry,
            CommandSourceStack source,
            ExecutionContext<CommandSourceStack> execContext
    ) throws CommandSyntaxException {
        if (entry instanceof BuildContextsAccessor<?> bca) {
            @SuppressWarnings("unchecked")
            ContextChain<CommandSourceStack> chain =
                    ((BuildContextsAccessor<CommandSourceStack>) (Object) bca).functionCompiler$getCommand();
            Command<CommandSourceStack> cmd = chain.getTopContext().getCommand();
            if (cmd != null) {
                return cmd.run(chain.getTopContext().copyFor(source));
            }
        }
        entry.bind(source).execute(execContext, null);
        return 0;
    }

    private static boolean canDebit(ExecutionContext<CommandSourceStack> execContext) {
        if (execContext == null) {
            return true;
        }
        @SuppressWarnings("unchecked")
        ExecutionContextAccessor<CommandSourceStack> accessor =
                (ExecutionContextAccessor<CommandSourceStack>) (Object) execContext;
        if (accessor.functionCompiler$getCommandQuota() <= 0) {
            return false;
        }
        execContext.incrementCost();
        return true;
    }
}
