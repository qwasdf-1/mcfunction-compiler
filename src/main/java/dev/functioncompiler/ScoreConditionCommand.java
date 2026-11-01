package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.advancements.predicates.MinMaxBounds;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.resources.Identifier;
import net.minecraft.server.ServerScoreboard;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;
import net.minecraft.world.scores.ScoreHolder;

final class ScoreConditionCommand implements FusableCommand {
    enum Operator {
        EQUALS,
        LESS_THAN,
        LESS_THAN_OR_EQUAL,
        GREATER_THAN,
        GREATER_THAN_OR_EQUAL
    }

    private final ContextChain<CommandSourceStack> fallbackChain;
    private final ScoreHolder targetHolder;
    private final boolean isTargetSelf;
    private final String targetObjective;
    private final Operator operator;
    private final ScoreHolder sourceHolder;
    private final boolean isSourceSelf;
    private final String sourceObjective;
    private final MinMaxBounds.Ints range;
    private final boolean unless;
    private final Command<CommandSourceStack> innerCommand;
    private final Identifier functionId;

    ScoreConditionCommand(
            ContextChain<CommandSourceStack> fallbackChain,
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            String targetObjective,
            Operator operator,
            ScoreHolder sourceHolder,
            boolean isSourceSelf,
            String sourceObjective,
            MinMaxBounds.Ints range,
            boolean unless,
            Command<CommandSourceStack> innerCommand,
            Identifier functionId
    ) {
        this.fallbackChain = fallbackChain;
        this.targetHolder = targetHolder;
        this.isTargetSelf = isTargetSelf;
        this.targetObjective = targetObjective;
        this.operator = operator;
        this.sourceHolder = sourceHolder;
        this.isSourceSelf = isSourceSelf;
        this.sourceObjective = sourceObjective;
        this.range = range;
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
        if (hasMissingObjectiveOrHolder(source)) {
            return fallbackChain.executeAll(source, ExecutionCommandSource.resultConsumer());
        }

        boolean matched = isConditionMet(source);
        if (unless == matched) {
            return 0;
        }

        int result = innerCommand.run(context);
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }

    private boolean hasMissingObjectiveOrHolder(CommandSourceStack source) {
        ScoreHolder target = resolveHolder(source, isTargetSelf, targetHolder);
        ServerScoreboard scoreboard = source.getServer().getScoreboard();
        if (target == null || scoreboard.getObjective(targetObjective) == null) {
            return true;
        }
        if (range == null) {
            ScoreHolder src = resolveHolder(source, isSourceSelf, sourceHolder);
            return src == null || scoreboard.getObjective(sourceObjective) == null;
        }
        return false;
    }

    private boolean isConditionMet(CommandSourceStack source) {
        ScoreHolder target = resolveHolder(source, isTargetSelf, targetHolder);
        ServerScoreboard scoreboard = source.getServer().getScoreboard();
        Objective targetObj = scoreboard.getObjective(targetObjective);
        ReadOnlyScoreInfo targetInfo = scoreboard.getPlayerScoreInfo(target, targetObj);
        if (targetInfo == null) {
            return false;
        }

        if (range != null) {
            return range.matches(targetInfo.value());
        }

        ScoreHolder src = resolveHolder(source, isSourceSelf, sourceHolder);
        Objective sourceObj = scoreboard.getObjective(sourceObjective);
        ReadOnlyScoreInfo sourceInfo = scoreboard.getPlayerScoreInfo(src, sourceObj);
        return sourceInfo != null && compareScores(targetInfo.value(), sourceInfo.value(), operator);
    }

    private static ScoreHolder resolveHolder(
            CommandSourceStack source,
            boolean isSelf,
            ScoreHolder staticHolder
    ) {
        if (isSelf) {
            Entity entity = source.getEntity();
            return entity != null ? entity : null;
        }
        return staticHolder;
    }

    private static boolean compareScores(int target, int source, Operator op) {
        return switch (op) {
            case EQUALS -> target == source;
            case LESS_THAN -> target < source;
            case LESS_THAN_OR_EQUAL -> target <= source;
            case GREATER_THAN -> target > source;
            case GREATER_THAN_OR_EQUAL -> target >= source;
        };
    }
}
