package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.ScoreboardCommandAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.ObjectiveArgument;
import net.minecraft.commands.arguments.OperationArgument;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.server.commands.CommandResponseTracker.ElementType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreAccess;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;

final class ScoreOperationCommand implements FusableCommand {
    private final Command<CommandSourceStack> vanillaCommand;
    private final ScoreHolder targetHolder;
    private final boolean isTargetSelf;
    private final OperationArgument.Operation operation;
    private final ScoreHolder sourceHolder;
    private final boolean isSourceSelf;
    private final Identifier functionId;

    ScoreOperationCommand(
            Command<CommandSourceStack> vanillaCommand,
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            OperationArgument.Operation operation,
            ScoreHolder sourceHolder,
            boolean isSourceSelf,
            Identifier functionId
    ) {
        this.vanillaCommand = vanillaCommand;
        this.targetHolder = targetHolder;
        this.isTargetSelf = isTargetSelf;
        this.operation = operation;
        this.sourceHolder = sourceHolder;
        this.isSourceSelf = isSourceSelf;
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

        ScoreHolder src;
        if (isSourceSelf) {
            Entity entity = source.getEntity();
            if (entity == null) {
                return vanillaCommand.run(context);
            }
            src = entity;
        } else {
            src = this.sourceHolder;
        }

        Objective targetObj = ObjectiveArgument.getWritableObjective(context, "targetObjective");
        Objective sourceObj = ObjectiveArgument.getObjective(context, "sourceObjective");
        Scoreboard scoreboard = source.getServer().getScoreboard();
        ScoreAccess targetScore = scoreboard.getOrCreatePlayerScore(target, targetObj);
        ScoreAccess sourceScore = scoreboard.getOrCreatePlayerScore(src, sourceObj);

        operation.apply(targetScore, sourceScore);

        CommandResponseTracker<ScoreHolder> response = CommandResponseTracker.create();
        response.track(target, targetScore.get());
        int result = response.sendFeedback(
                source,
                true,
                ElementType.ANY,
                ScoreboardCommandAccessor.functionCompiler$getScoreOperationResponse(),
                targetObj
        );
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }
}
