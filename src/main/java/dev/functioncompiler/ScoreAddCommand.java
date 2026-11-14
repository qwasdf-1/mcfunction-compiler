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
    private final String objectiveName;
    private final ResearchMode researchMode;

    private enum ResearchMode {
        NORMAL, DELEGATING_WRAPPER, FAST_OBJECTIVE_LOOKUP
    }

    private static ResearchMode researchMode(Identifier id, String objectiveName,
                                             ScoreHolder holder, boolean isSelf,
                                             Operation operation) {
        if (!ProbeConfiguration.scoreAddAttributionEnabled() || id == null) {
            return ResearchMode.NORMAL;
        }
        if ("fc_attr_delegate".equals(id.getNamespace())) {
            return ResearchMode.DELEGATING_WRAPPER;
        }
        if ("fc_attr_fastobj".equals(id.getNamespace())
                && "fc_sched".equals(objectiveName)
                && holder != null && !isSelf && operation == Operation.ADD) {
            return ResearchMode.FAST_OBJECTIVE_LOOKUP;
        }
        return ResearchMode.NORMAL;
    }

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
        this(vanillaCommand, holder, isSelfSelector, operation, amount, functionId, null);
    }

    ScoreAddCommand(
            Command<CommandSourceStack> vanillaCommand,
            ScoreHolder holder,
            boolean isSelfSelector,
            Operation operation,
            int amount,
            Identifier functionId,
            String objectiveName
    ) {
        this.vanillaCommand = vanillaCommand;
        this.holder = holder;
        this.isSelfSelector = isSelfSelector;
        this.operation = operation;
        this.amount = amount;
        this.functionId = functionId;
        this.objectiveName = objectiveName;
        this.researchMode = researchMode(functionId, objectiveName, holder, isSelfSelector, operation);
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
                || researchMode == ResearchMode.DELEGATING_WRAPPER) {
            // Measures cost of the ScoreAddCommand callback layer without
            // changing the underlying scoreboard command or scheduler.
            return vanillaCommand.run(context);
        }

        boolean diagnose = ProbeConfiguration.scoreAddPhaseTimersForFunction(functionId);
        long t0 = diagnose ? System.nanoTime() : 0L;
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

        Scoreboard scoreboard = source.getServer().getScoreboard();
        Objective objective;
        if (researchMode == ResearchMode.FAST_OBJECTIVE_LOOKUP) {
            // Resolve against the CURRENT server scoreboard on every call.
            // Never retain an Objective across datapack/reload or remove/readd.
            // Missing or read-only objectives fall back to vanilla Brigadier
            // argument validation and its exact CommandSyntaxException.
            Objective candidate = scoreboard.getObjective(objectiveName);
            objective = candidate != null && !candidate.getCriteria().isReadOnly()
                    ? candidate
                    : ObjectiveArgument.getWritableObjective(context, "objective");
        } else {
            objective = ObjectiveArgument.getWritableObjective(context, "objective");
        }
        long t1 = diagnose ? System.nanoTime() : 0L;
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

        long t2 = diagnose ? System.nanoTime() : 0L;
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
        if (diagnose) {
            long t3 = System.nanoTime();
            ProbeMetrics.scoreAddPhases(t1 - t0, t2 - t1, t3 - t2);
        }
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }
}
