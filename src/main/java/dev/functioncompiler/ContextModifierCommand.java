package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.resources.Identifier;

import java.util.List;

final class ContextModifierCommand implements FusableCommand {
    @FunctionalInterface
    interface Transformation {
        CommandSourceStack apply(CommandContext<CommandSourceStack> context, CommandSourceStack source)
                throws CommandSyntaxException;
    }

    private final ContextChain<CommandSourceStack> fallbackChain;
    private final List<Transformation> transformations;
    private final Command<CommandSourceStack> innerCommand;
    private final Identifier functionId;

    ContextModifierCommand(
            ContextChain<CommandSourceStack> fallbackChain,
            List<Transformation> transformations,
            Command<CommandSourceStack> innerCommand,
            Identifier functionId
    ) {
        this.fallbackChain = fallbackChain;
        this.transformations = transformations;
        this.innerCommand = innerCommand;
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
        // The fallback bypasses the execution queue, so it must only run when
        // nothing that motivated the compile is active; a timing-only or
        // bytecode-only arm still needs the compiled (quota-exact) path.
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.scoreAddTimingEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()
                && !ProbeConfiguration.bytecodeRegionPrototypeEnabled()) {
            return fallbackChain.executeAll(
                    context.getSource(),
                    ExecutionCommandSource.resultConsumer()
            );
        }

        CommandSourceStack currentSource = context.getSource();
        for (Transformation transformation : transformations) {
            currentSource = transformation.apply(context, currentSource);
            if (currentSource == null) {
                // Vanilla resolves this stage to no sources: the stage debit
                // was charged but no per-source ExecuteCommand follows. The
                // compiled chain always pays the per-source debit, so no stage
                // charge here keeps the per-line total at one.
                return 0;
            }
        }

        // One debit per folded modifier stage, then the same quota gate as the
        // other inlined commands: the inner command runs only while the
        // remaining quota has not gone negative.
        ExecutionContextBridge.chargeInlinedModifierStages(transformations.size());
        if (!ExecutionContextBridge.inlinedInnerRunnable()) {
            return 0;
        }

        int result = innerCommand.run(context.copyFor(currentSource));
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }
}
