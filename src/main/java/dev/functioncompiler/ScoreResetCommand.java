package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.ScoreboardCommandAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.ObjectiveArgument;
import net.minecraft.resources.Identifier;
import net.minecraft.server.ServerScoreboard;
import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;

final class ScoreResetCommand implements FusableCommand {
    private final Command<CommandSourceStack> vanillaCommand;
    private final ScoreHolder targetHolder;
    private final boolean isTargetSelf;
    private final boolean hasObjective;
    private final Identifier functionId;

    ScoreResetCommand(
            Command<CommandSourceStack> vanillaCommand,
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            boolean hasObjective,
            Identifier functionId
    ) {
        this.vanillaCommand = vanillaCommand;
        this.targetHolder = targetHolder;
        this.isTargetSelf = isTargetSelf;
        this.hasObjective = hasObjective;
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
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()) {
            return vanillaCommand.run(context);
        }

        CommandSourceStack source = context.getSource();
        ScoreHolder target;
        if (isTargetSelf) {
            Entity entity = source.getEntity();
            if (entity == null) {
                return vanillaCommand.run(context);
            }
            target = entity;
        } else {
            target = this.targetHolder;
        }

        ServerScoreboard scoreboard = source.getServer().getScoreboard();
        CommandResponseTracker<ScoreHolder> response = CommandResponseTracker.create();
        int result;
        if (hasObjective) {
            Objective objective = ObjectiveArgument.getObjective(context, "objective");
            scoreboard.resetSinglePlayerScore(target, objective);
            response.track(target);
            result = response.sendFeedback(
                    source,
                    true,
                    ScoreboardCommandAccessor.functionCompiler$getScoreResetResponse(),
                    objective
            );
        } else {
            scoreboard.resetAllPlayerScores(target);
            response.track(target);
            result = response.sendFeedback(
                    source,
                    true,
                    ScoreboardCommandAccessor.functionCompiler$getScoreResetAllResponse()
            );
        }

        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }
}
