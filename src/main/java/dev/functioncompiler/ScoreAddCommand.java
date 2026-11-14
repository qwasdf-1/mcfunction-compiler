package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.ObjectiveArgument;
import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreAccess;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;
import net.minecraft.server.commands.CommandResponseTracker.ElementType;
import dev.functioncompiler.mixin.ScoreboardCommandAccessor;
import net.minecraft.resources.Identifier;

final class ScoreAddCommand implements FusableCommand {
    enum Operation {
        ADD,
        SET,
        REMOVE
    }

    private final Command<CommandSourceStack> vanillaCommand;
    private final ScoreHolder holder;
    private final boolean isSelfSelector;
    private final Operation operation;
    private final int amount;
    private final Identifier functionId;
    private final boolean useLegacyFlagLookups;

    ScoreAddCommand(
            Command<CommandSourceStack> vanillaCommand,
            ScoreHolder holder,
            int amount,
            Identifier functionId
    ) {
        this(vanillaCommand, holder, false, Operation.ADD, amount, functionId);
    }

    ScoreAddCommand(
            Command<CommandSourceStack> vanillaCommand,
            ScoreHolder holder,
            boolean isSelfSelector,
            int amount,
            Identifier functionId
    ) {
        this(vanillaCommand, holder, isSelfSelector, Operation.ADD, amount, functionId);
    }

    ScoreAddCommand(
            Command<CommandSourceStack> vanillaCommand,
            ScoreHolder holder,
            boolean isSelfSelector,
            Operation operation,
            int amount,
            Identifier functionId
    ) {
        this.vanillaCommand = vanillaCommand;
        this.holder = holder;
        this.isSelfSelector = isSelfSelector;
        this.operation = operation;
        this.amount = amount;
        this.functionId = functionId;
        this.useLegacyFlagLookups = ProbeConfiguration.legacyScoreAddLookupForFunction(functionId);
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context) throws CommandSyntaxException {
        if (useLegacyFlagLookups
                ? ProbeConfiguration.scoreAddTimingEnabledLegacy()
                : ProbeConfiguration.scoreAddTimingEnabled()) {
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
        if (!(useLegacyFlagLookups
                ? ProbeConfiguration.scoreAddPrototypeEnabledLegacy()
                : ProbeConfiguration.scoreAddPrototypeEnabled())) {
            return vanillaCommand.run(context);
        }

        CommandSourceStack source = context.getSource();
        ScoreHolder targetHolder;
        if (isSelfSelector) {
            Entity entity = source.getEntity();
            if (entity == null) {
                return vanillaCommand.run(context);
            }
            targetHolder = entity;
        } else {
            targetHolder = this.holder;
        }

        Objective objective = ObjectiveArgument.getWritableObjective(context, "objective");
        Scoreboard scoreboard = source.getServer().getScoreboard();
        ScoreAccess score = scoreboard.getOrCreatePlayerScore(targetHolder, objective);
        int newScore;
        CommandResponseTracker.MessagesWithArgs<ScoreHolder, Objective, Integer> responseMessages;
        switch (operation) {
            case SET -> {
                score.set(amount);
                newScore = amount;
                responseMessages = ScoreboardCommandAccessor.functionCompiler$getScoreSetResponse();
            }
            case REMOVE -> {
                newScore = score.add(-amount);
                responseMessages = ScoreboardCommandAccessor.functionCompiler$getScoreRemoveResponse();
            }
            default -> {
                newScore = score.add(amount);
                responseMessages = ScoreboardCommandAccessor.functionCompiler$getScoreAddResponse();
            }
        }

        CommandResponseTracker<ScoreHolder> response = CommandResponseTracker.create();
        response.track(targetHolder, newScore);
        int result = response.sendFeedback(
                source,
                true,
                ElementType.ANY,
                responseMessages,
                objective,
                amount
        );
        if (useLegacyFlagLookups
                ? ProbeConfiguration.scoreAddMetricsEnabledLegacy()
                : ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }
}
