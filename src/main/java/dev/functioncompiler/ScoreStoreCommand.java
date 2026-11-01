package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.resources.Identifier;
import net.minecraft.server.ServerScoreboard;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreAccess;
import net.minecraft.world.scores.ScoreHolder;

final class ScoreStoreCommand implements FusableCommand {
    private final ContextChain<CommandSourceStack> fallbackChain;
    private final ScoreHolder targetHolder;
    private final boolean isTargetSelf;
    private final String objectiveName;
    private final boolean isResult;
    private final Command<CommandSourceStack> innerCommand;
    private final Identifier functionId;

    ScoreStoreCommand(
            ContextChain<CommandSourceStack> fallbackChain,
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            String objectiveName,
            boolean isResult,
            Command<CommandSourceStack> innerCommand,
            Identifier functionId
    ) {
        this.fallbackChain = fallbackChain;
        this.targetHolder = targetHolder;
        this.isTargetSelf = isTargetSelf;
        this.objectiveName = objectiveName;
        this.isResult = isResult;
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
        ScoreHolder target = resolveHolder(source);
        ServerScoreboard scoreboard = source.getServer().getScoreboard();
        Objective objective = scoreboard.getObjective(objectiveName);
        if (target == null || objective == null) {
            return fallbackChain.executeAll(source, ExecutionCommandSource.resultConsumer());
        }

        int result;
        try {
            result = innerCommand.run(context);
        } catch (CommandSyntaxException exception) {
            ScoreAccess score = scoreboard.getOrCreatePlayerScore(target, objective);
            score.set(0);
            throw exception;
        }

        int storedValue = isResult ? result : 1;
        ScoreAccess score = scoreboard.getOrCreatePlayerScore(target, objective);
        score.set(storedValue);

        if (source.callback() != null) {
            source.callback().onResult(true, result);
        }

        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }

    private ScoreHolder resolveHolder(CommandSourceStack source) {
        if (isTargetSelf) {
            Entity entity = source.getEntity();
            return entity != null ? entity : null;
        }
        return targetHolder;
    }
}
