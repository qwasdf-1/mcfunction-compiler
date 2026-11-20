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
import java.util.HashMap;
import java.util.Map;

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
        private Objective sourceObjective;
        private Map<ScoreValueRevisionAccess.Key, CachedSourceValue> cachedSources;

        // Immutable snapshot; only valid while the exact objective identity
        // and the watched slot's scoreboard mutation revision still match.
        private record CachedSourceValue(Objective objective, long revision, int value) {}

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
                    traceReturn(instruction, 0);
                    return SKIP;
                }
                context.incrementCost();
                if (quota() < 0) {
                    TypedScoreIR.skippedConditional();
                    traceReturn(instruction, 0);
                    return SKIP;
                }
            }

            current = instruction;
            objective = selected;
            // Every lookup is deliberately fresh. Even a disjoint preceding
            // command can run externally observable feedback/listener logic.
            access = scoreboard.getOrCreatePlayerScore(instruction.holder(), selected);
            if (instruction instanceof TypedScoreIR.Binary binary) {
                sourceObjective = second;
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

        /**
         * IR-010: optionally reuse a source read from an earlier instruction
         * in THIS compiled region, but only while the server scoreboard's
         * watched revision and exact Objective instance still match. An
         * intervening ScoreAccess.set/add or scoreboard reset invalidates
         * the snapshot even if triggered by a synchronous result callback.
         *
         * We deliberately still call getOrCreatePlayerScore in begin() for
         * every instruction to preserve the vanilla scoreboard row-creation
         * and command feedback behavior. This is only a pure value read
         * optimization; never defer or coalesce writes.
         */
        int sourceOperand() {
            if (!TypedScoreIR.scoreCacheEnabled()
                    || !(current instanceof TypedScoreIR.Binary binary)
                    || !(scoreboard instanceof ScoreValueRevisionAccess versions)) {
                return sourceAccess.get();
            }
            var key = new ScoreValueRevisionAccess.Key(
                    binary.sourceHolder().getScoreboardName(),
                    binary.sourceObjective());
            long revision = versions.functionCompiler$watch(key);
            if (revision < 0) return sourceAccess.get();  // fail closed
            if (cachedSources == null) cachedSources = new HashMap<>();
            CachedSourceValue entry = cachedSources.get(key);
            if (entry != null && entry.revision() == revision
                    && entry.objective() == sourceObjective) {
                TypedScoreIR.cacheHit();
                return entry.value();
            }
            if (entry != null) TypedScoreIR.cacheInvalidated();
            // The exact 26.3 ScoreAccess.get implementation is a pure read.
            // ScoreAccess is obtained afresh each instruction by begin().
            int fresh = sourceAccess.get();
            cachedSources.put(key, new CachedSourceValue(sourceObjective, revision, fresh));
            TypedScoreIR.cacheMiss();
            return fresh;
        }

        private void traceReturn(TypedScoreIR.Instruction instruction, int result) {
            TraceCallbacks tracer = context.tracer();
            if (tracer != null) {
                tracer.onReturn(frame.depth(), instruction.vanilla().commandInput(), result);
            }
        }

        void finish(int newScore) {
            TypedScoreIR.Instruction instruction = current;
            TraceCallbacks tracer = context.tracer();
            try {
                int result;
                if (TypedScoreIR.singletonFeedbackEnabled()) {
                    // Vanilla CommandResponseTracker gets exactly ONE tracked
                    // holder and ElementType.ANY: elementCount=1 even when
                    // newScore is zero. Its throwIfZero(1) is a no-op; its
                    // totalValue is newScore and dispatch selects onSingle.
                    // Preserve sendSuccess/broadcast, deferred message
                    // formatting and subsequent trace callback verbatim.
                    var holder = instruction.holder();
                    var resolvedObjective = objective;
                    if (instruction instanceof TypedScoreIR.Binary) {
                        var message = ScoreboardCommandAccessor
                                .functionCompiler$getScoreOperationResponse();
                        source.sendSuccess(() -> message.onSuccess().onSingle()
                                .create(holder, newScore, resolvedObjective), true);
                    } else {
                        TypedScoreIR.Mutation mutation =
                                instruction instanceof TypedScoreIR.Conditional guard
                                        ? guard.mutation() : (TypedScoreIR.Mutation) instruction;
                        var message = switch (mutation.operation()) {
                            case ADD -> ScoreboardCommandAccessor.functionCompiler$getScoreAddResponse();
                            case REMOVE -> ScoreboardCommandAccessor.functionCompiler$getScoreRemoveResponse();
                            case SET -> ScoreboardCommandAccessor.functionCompiler$getScoreSetResponse();
                        };
                        source.sendSuccess(() -> message.onSuccess().onSingle()
                                .create(holder, newScore, resolvedObjective, mutation.amount()), true);
                    }
                    result = newScore;
                    TypedScoreIR.singletonFeedbackUsed();
                } else {
                    CommandResponseTracker<net.minecraft.world.scores.ScoreHolder> response =
                            CommandResponseTracker.create();
                    response.track(instruction.holder(), newScore);
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
                    TypedScoreIR.trackerFeedbackUsed();
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
                sourceObjective = null;
            }
        }
    }
}
