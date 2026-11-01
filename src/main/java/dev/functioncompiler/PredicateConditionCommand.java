package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.resources.Identifier;

final class PredicateConditionCommand implements FusableCommand {
    @FunctionalInterface
    interface PredicateEvaluator {
        Boolean evaluate(CommandSourceStack source) throws CommandSyntaxException;
    }

    private final ContextChain<CommandSourceStack> fallbackChain;
    private final PredicateEvaluator evaluator;
    private final boolean unless;
    private final Command<CommandSourceStack> innerCommand;
    private final Identifier functionId;

    PredicateConditionCommand(
            ContextChain<CommandSourceStack> fallbackChain,
            PredicateEvaluator evaluator,
            boolean unless,
            Command<CommandSourceStack> innerCommand,
            Identifier functionId
    ) {
        this.fallbackChain = fallbackChain;
        this.evaluator = evaluator;
        this.unless = unless;
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
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()) {
            return fallbackChain.executeAll(
                    context.getSource(),
                    ExecutionCommandSource.resultConsumer()
            );
        }

        CommandSourceStack source = context.getSource();
        Boolean matched;
        try {
            matched = evaluator.evaluate(source);
        } catch (CommandSyntaxException exception) {
            return fallbackChain.executeAll(source, ExecutionCommandSource.resultConsumer());
        }

        if (matched == null) {
            return fallbackChain.executeAll(source, ExecutionCommandSource.resultConsumer());
        }

        if (unless == matched) {
            return 0;
        }

        int result = innerCommand.run(context);
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }
}
