package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.ExecutionContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;

import java.util.List;

final class TailCallLoopCommand implements FusableCommand {
    private final Command<CommandSourceStack> originalCommand;
    private final PlainTextFunction<CommandSourceStack> targetFunction;
    private final Identifier functionId;

    TailCallLoopCommand(
            Command<CommandSourceStack> originalCommand,
            PlainTextFunction<CommandSourceStack> targetFunction,
            Identifier functionId
    ) {
        this.originalCommand = originalCommand;
        this.targetFunction = targetFunction;
        this.functionId = functionId;
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context) throws CommandSyntaxException {
        if (ProbeConfiguration.scoreAddTimingEnabled()) {
            long started = System.nanoTime();
            try {
                return runUntimed(context);
            } finally {
                ProbeMetrics.scoreAddTimed(functionId, System.nanoTime() - started);
            }
        }
        return runUntimed(context);
    }

    private int runUntimed(CommandContext<CommandSourceStack> context)
            throws CommandSyntaxException {
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()) {
            return originalCommand.run(context);
        }

        ExecutionContext<CommandSourceStack> execContext = ExecutionContextBridge.currentContext();
        if (execContext == null) {
            return originalCommand.run(context);
        }

        ExecutionContextAccessor<?> accessor = (ExecutionContextAccessor<?>) (Object) execContext;
        if (accessor.functionCompiler$getCommandQuota() <= 0) {
            return 0;
        }

        execContext.incrementCost();
        List<UnboundEntryAction<CommandSourceStack>> entries = targetFunction.entries();
        int lastIndex = entries.size() - 1;
        for (int i = 0; i < lastIndex; i++) {
            if (accessor.functionCompiler$getCommandQuota() <= 0) {
                return 0;
            }
            execContext.incrementCost();
            executeEntry(entries.get(i), context.getSource());
        }

        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return 1;
    }

    @SuppressWarnings("unchecked")
    private void executeEntry(
            UnboundEntryAction<CommandSourceStack> entry,
            CommandSourceStack source
    ) throws CommandSyntaxException {
        if (entry instanceof BuildContextsAccessor<?> bca) {
            var chain = ((BuildContextsAccessor<CommandSourceStack>) (Object) bca).functionCompiler$getCommand();
            chain.getTopContext().getCommand().run(chain.getTopContext().copyFor(source));
        }
    }
}
