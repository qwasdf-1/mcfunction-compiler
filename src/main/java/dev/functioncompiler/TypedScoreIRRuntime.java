package dev.functioncompiler;

import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.ExecutionContextAccessor;
import dev.functioncompiler.mixin.ScoreboardCommandAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.TraceCallbacks;
import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.server.commands.CommandResponseTracker.ElementType;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;
import net.minecraft.world.scores.ScoreAccess;
import net.minecraft.world.scores.Scoreboard;

/**
 * Shared IR interpreter/ASM semantic boundary. All direct instructions still
 * perform vanilla quota debits, trace, per-command scoreboard operations,
 * response tracking and error handling. No cross-command ScoreAccess caching.
 */
final class TypedScoreIRRuntime {
    static final int STOP = 0;
    static final int DIRECT = 1;
    static final int FALLBACK = 2;
    static final int SKIP = 3;

    private TypedScoreIRRuntime() {}

    static final class State {
        private final CommandSourceStack source;
        private final ExecutionContext<CommandSourceStack> context;
        private final Frame frame;
        private final Scoreboard scoreboard;
        private TypedScoreIR.Instruction current;
        private Objective objective;
        private ScoreAccess access;
        private ScoreAccess sourceAccess;

        State(CommandSourceStack source, ExecutionContext<CommandSourceStack> context, Frame frame) {
            this.source = source;
            this.context = context;
            this.frame = frame;
            this.scoreboard = source.getServer().getScoreboard();
        }

        private int quota() {
            return ((ExecutionContextAccessor<CommandSourceStack>) (Object) context)
                    .functionCompiler$getCommandQuota();
        }

        /**
         * Guard all runtime objective assumptions before any direct-path
         * quota debit or score write. On violation, execute the *original*
         * validated command with its original vanilla/error behavior once.
         */
        int begin(TypedScoreIR.Instruction instruction) {
            if (quota() <= 0) return STOP;
            Objective selected = scoreboard.getObjective(instruction.objective());
            if (selected == null || selected.getCriteria().isReadOnly()) {
                return original(instruction);
            }

            Objective second = null;
            if (instruction instanceof TypedScoreIR.Binary binary) {
                second = scoreboard.getObjective(binary.sourceObjective());
            } else if (instruction instanceof TypedScoreIR.Conditional condition) {
                second = scoreboard.getObjective(condition.conditionObjective());
            }
            if (!(instruction instanceof TypedScoreIR.Mutation) && second == null) {
                return original(instruction);
            }

            TraceCallbacks tracer = context.tracer();
            if (tracer != null) {
                tracer.onCommand(frame.depth(), instruction.vanilla().commandInput());
            }
            context.incrementCost();

            // Vanilla charges the score condition stage even when false. A
            // true condition generates an additional terminal-command debit;
            // the existing compiled ScoreConditionCommand does the same.
            if (instruction instanceof TypedScoreIR.Conditional condition) {
                ReadOnlyScoreInfo info = scoreboard.getPlayerScoreInfo(
                        condition.conditionHolder(), second);
                boolean matched = info != null && condition.range().matches(info.value());
                if (matched == condition.unless()) {
                    TypedScoreIR.skippedConditional();
                    traceReturn(0);
                    return SKIP;
                }
                context.incrementCost();
                if (quota() < 0) {
                    TypedScoreIR.skippedConditional();
                    traceReturn(0);
                    return SKIP;
                }
            }

            current = instruction;
            objective = selected;
            // Every lookup is deliberately fresh. Even a disjoint preceding
            // command can run externally observable feedback/listener logic.
            access = scoreboard.getOrCreatePlayerScore(instruction.holder(), selected);
            if (instruction instanceof TypedScoreIR.Binary binary) {
                sourceAccess = scoreboard.getOrCreatePlayerScore(binary.sourceHolder(), second);
            }
            TypedScoreIR.step(instruction);
            return DIRECT;
        }

        private int original(TypedScoreIR.Instruction instruction) {
            TypedScoreIR.fallback();
            return FusedRegionPrototype.executeCommand(
                    instruction.vanilla(), source, context, frame
            ) ? FALLBACK : STOP;
        }

        ScoreAccess access() { return access; }
        ScoreAccess sourceAccess() { return sourceAccess; }

        private void traceReturn(int result) {
            TraceCallbacks tracer = context.tracer();
            if (tracer != null && current != null) {
                tracer.onReturn(frame.depth(), current.vanilla().commandInput(), result);
            }
        }

        void finish(int newScore) {
            TypedScoreIR.Instruction instruction = current;
            CommandResponseTracker<net.minecraft.world.scores.ScoreHolder> response =
                    CommandResponseTracker.create();
            response.track(instruction.holder(), newScore);
            TraceCallbacks tracer = context.tracer();
            try {
                int result;
                if (instruction instanceof TypedScoreIR.Binary) {
                    result = response.sendFeedback(
                            source, true, ElementType.ANY,
                            ScoreboardCommandAccessor.functionCompiler$getScoreOperationResponse(),
                            objective
                    );
                } else {
                    TypedScoreIR.Mutation mutation =
                            instruction instanceof TypedScoreIR.Conditional guard
                                    ? guard.mutation() : (TypedScoreIR.Mutation) instruction;
                    var message = switch (mutation.operation()) {
                        case ADD -> ScoreboardCommandAccessor.functionCompiler$getScoreAddResponse();
                        case REMOVE -> ScoreboardCommandAccessor.functionCompiler$getScoreRemoveResponse();
                        case SET -> ScoreboardCommandAccessor.functionCompiler$getScoreSetResponse();
                    };
                    result = response.sendFeedback(
                            source, true, ElementType.ANY, message, objective, mutation.amount()
                    );
                }
                if (tracer != null) {
                    tracer.onReturn(frame.depth(), instruction.vanilla().commandInput(), result);
                }
            } catch (CommandSyntaxException error) {
                source.handleError(error, false, tracer);
            } finally {
                current = null;
                objective = null;
                access = null;
                sourceAccess = null;
            }
        }
    }
}
