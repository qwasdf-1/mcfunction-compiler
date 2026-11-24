package dev.functioncompiler;

import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.ExecutionContextAccessor;
import dev.functioncompiler.mixin.ScoreboardCommandAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.CommandQueueEntry;
import net.minecraft.commands.execution.EntryAction;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.TraceCallbacks;
import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.server.commands.CommandResponseTracker.ElementType;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;
import net.minecraft.world.scores.ScoreAccess;
import net.minecraft.world.scores.Scoreboard;
import net.minecraft.world.scores.ScoreHolder;
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

    private static final boolean REENTRANT_SAFE =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_REENTRANT_SAFE"));

    /**
     * Exceptional-only queue cursor. When a scoreboard callback queues work
     * during an IR region, it must run before the NEXT source instruction.
     * Stage one already-validated typed instruction as its own Minecraft
     * queue action, then lazily stage the next cursor. This preserves the
     * normal depth-first staging boundary without touching a formerly
     * rewritten Brigadier ScoreConditionCommand callback (whose old
     * fallbackChain can be self-referential after command wrapping).
     *
     * We preserve the original parsed fallback in State for runtime
     * objective changes; this queue continuation is for accepted typed
     * commands on the normal fast semantic path, not unknown commands.
     */
    private record QueuedTail(
            CommandSourceStack source,
            TypedScoreIR.Instruction[] instructions,
            int index
    ) implements EntryAction<CommandSourceStack> {
        @Override
        public void execute(
                ExecutionContext<CommandSourceStack> context, Frame frame
        ) {
            if (index >= instructions.length) return;
            TypedScoreIR.Instruction current = instructions[index];
            context.queueNext(new CommandQueueEntry<>(frame,
                    (execution, commandFrame) -> {
                        TypedScoreIRRuntime.State state = new TypedScoreIRRuntime.State(
                                source, execution, commandFrame,
                                new TypedScoreIR.Instruction[]{current});
                        TypedScoreIR.executeTypedStep(current, state);
                    }));
            if (index + 1 < instructions.length) {
                context.queueNext(new CommandQueueEntry<>(
                        frame, new QueuedTail(source, instructions, index + 1)));
            }
            TypedScoreIR.reentrantQueuedStep();
        }
    }

    static final class State {
        private final CommandSourceStack source;
        private final ExecutionContext<CommandSourceStack> context;
        private final Frame frame;
        private final Scoreboard scoreboard;
        private final TypedScoreIR.Instruction[] instructions;
        private final long initialQueueEpoch;
        private int nextIndex;
        private TypedScoreIR.Instruction current;
        // IR-037: the original command's immutable shape/feedback metadata,
        // computed once per compiled region (only queued tails build it on demand).
        private TypedIRPreparedSteps.Prepared currentPrepared;
        private Objective objective;
        private ScoreAccess access;
        private ScoreAccess sourceAccess;
        private Objective sourceObjective;
        // IR-018: no entity-derived holder can be cached at compilation time.
        // Resolve @s against the actual execution source for each instruction.
        private ScoreHolder targetResolved;
        private ScoreHolder sourceResolved;
        private Map<ScoreValueRevisionAccess.Key, CachedSourceValue> cachedSources;
        // Per-invocation scratch, overwritten for every compound command.
        private Objective[] compoundObjectives;
        private ScoreHolder[] compoundHolders;

        // Immutable snapshot; only valid while the exact objective identity
        // and the watched slot's scoreboard mutation revision still match.
        private record CachedSourceValue(Objective objective, long revision, int value) {}

        State(
                CommandSourceStack source,
                ExecutionContext<CommandSourceStack> context,
                Frame frame,
                TypedScoreIR.Instruction[] instructions
        ) {
            this.source = source;
            this.context = context;
            this.frame = frame;
            this.instructions = instructions;
            this.scoreboard = source.getServer().getScoreboard();
            this.initialQueueEpoch = REENTRANT_SAFE && context instanceof ReentrantQueueEpoch epoch
                    ? epoch.functionCompiler$queuedWorkEpoch() : 0L;
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
            // Exceptional reentrant queue tails contain original source
            // instructions, not the compiled Plan. They are never the hot path.
            return begin(TypedIRPreparedSteps.prepare(instruction));
        }

        /**
         * IR-037: runtime work uses predecoded compiler metadata instead of
         * repeatedly inspecting Conditional/Binary/Mutation instruction
         * classes, recovering terminal commands and rediscovering holder/
         * objective metadata. Every OBJECTIVE/score lookup is still fresh,
         * and every listener, quota, trace, feedback and queue boundary remains.
         */
        int begin(TypedIRPreparedSteps.Prepared prepared) {
            TypedScoreIR.Instruction instruction = prepared.original();
            // Every new instruction is a possible vanilla interleaving point.
            // Once a callback has queued an entry during this compiled
            // action, return to the original queue before the NEXT command.
            // This is checked before objective resolution, command cost or
            // conditional guard evaluation to prevent duplicated effects.
            if (REENTRANT_SAFE && nextIndex > 0
                    && context instanceof ReentrantQueueEpoch epoch
                    && epoch.functionCompiler$queuedWorkEpoch() != initialQueueEpoch) {
                if (quota() > 0) {
                    context.queueNext(new CommandQueueEntry<>(
                            frame, new QueuedTail(source, instructions, nextIndex)));
                    TypedScoreIR.reentrantYield();
                }
                return STOP;
            }
            nextIndex++;
            if (quota() <= 0) return STOP;
            if (prepared.compound() != null) return startCompound(prepared);
            ScoreHolder target = prepared.targetSelf()
                    ? source.getEntity() : prepared.targetHolder();
            if (target == null) return original(instruction);
            Objective selected = scoreboard.getObjective(prepared.targetObjective());
            if (selected == null || selected.getCriteria().isReadOnly()) {
                return original(instruction);
            }

            // Preserve original lookup ORDER and all three potentially
            // distinct objectives: target, guard and binary operand.
            TypedScoreIR.Conditional condition = prepared.condition();
            boolean hasBinary = prepared.binary() != null;
            // IR-037: within THIS one command, the vanilla scoreboard
            // objective lookup is a pure name-map read. Nothing mutates the
            // scoreboard between target, guard and operand resolution.
            // Proven equal names can reuse the already resolved Objective.
            // At the NEXT source instruction we do all fresh lookups again.
            Objective guardObjective = null;
            if (condition != null) {
                if (prepared.guardSharesTargetObjective()) {
                    guardObjective = selected;
                    TypedScoreIR.objectiveLookupReused();
                } else {
                    guardObjective = scoreboard.getObjective(prepared.conditionObjective());
                }
            }
            ScoreHolder guardHolder = condition != null
                    ? (prepared.conditionSelf() ? source.getEntity()
                            : prepared.conditionHolder()) : null;
            // IR-038: a comparison has a second read-only predicate operand.
            // Its objective is resolved before quota or score effects, with
            // same-command name aliases only (never across source commands).
            boolean compares = condition != null && condition.comparison() != null;
            Objective comparisonObjective = null;
            ScoreHolder comparisonHolder = null;
            if (compares) {
                if (prepared.comparisonSharesTargetObjective()) {
                    comparisonObjective = selected;
                    TypedScoreIR.objectiveLookupReused();
                } else if (prepared.comparisonSharesGuardObjective()) {
                    comparisonObjective = guardObjective;
                    TypedScoreIR.objectiveLookupReused();
                } else {
                    comparisonObjective = scoreboard.getObjective(condition.comparisonObjective());
                }
                comparisonHolder = condition.comparisonSelf()
                        ? source.getEntity() : condition.comparisonHolder();
            }
            Objective operandObjective = null;
            if (hasBinary) {
                if (prepared.operandSharesTargetObjective()) {
                    operandObjective = selected;
                    TypedScoreIR.objectiveLookupReused();
                } else if (prepared.operandSharesGuardObjective()) {
                    operandObjective = guardObjective;
                    TypedScoreIR.objectiveLookupReused();
                } else if (prepared.operandSharesComparisonObjective()) {
                    operandObjective = comparisonObjective;
                    TypedScoreIR.objectiveLookupReused();
                } else {
                    operandObjective = scoreboard.getObjective(prepared.operandObjective());
                }
            }
            ScoreHolder operandHolder = hasBinary
                    ? (prepared.operandSelf() ? source.getEntity()
                            : prepared.operandHolder()) : null;
            if ((condition != null && (guardObjective == null || guardHolder == null))
                    || (compares && (comparisonObjective == null || comparisonHolder == null))
                    || (hasBinary && (operandObjective == null || operandHolder == null))) {
                return original(instruction);
            }

            TraceCallbacks tracer = context.tracer();
            if (tracer != null) {
                tracer.onCommand(frame.depth(), instruction.vanilla().commandInput());
            }
            context.incrementCost();

            // Vanilla charges the condition stage on a false predicate and a
            // second debit on its true branch; these are unchanged.
            if (condition != null) {
                ReadOnlyScoreInfo info = scoreboard.getPlayerScoreInfo(
                        guardHolder, guardObjective);
                boolean matched;
                if (!compares) {
                    matched = info != null && condition.range().matches(info.value());
                } else {
                    TypedScoreIR.comparisonEvaluated();
                    // Missing rows remain false (including X = X); do not
                    // create a row or turn a same-slot predicate into a
                    // compile-time unconditional command. Score reads are
                    // pure within this one predicate evaluation.
                    if (info == null) {
                        matched = false;
                    } else {
                        ReadOnlyScoreInfo right;
                        if (prepared.comparisonSameSlot()) {
                            right = info;
                            TypedScoreIR.comparisonReadReused();
                        } else {
                            right = scoreboard.getPlayerScoreInfo(comparisonHolder, comparisonObjective);
                        }
                        matched = right != null && ScoreConditionCommand.compareScores(
                                info.value(), right.value(), condition.comparison());
                    }
                }
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
            currentPrepared = prepared;
            objective = selected;
            targetResolved = target;
            // ScoreAccess is obtained per source command. Never cache it
            // across synchronous scoreboard callbacks or outside observers.
            access = scoreboard.getOrCreatePlayerScore(target, selected);
            if (hasBinary) {
                sourceObjective = operandObjective;
                sourceResolved = operandHolder;
                sourceAccess = scoreboard.getOrCreatePlayerScore(operandHolder, operandObjective);
            }
            TypedScoreIR.step(instruction);
            return DIRECT;
        }

        // Before ANY debit or observable effect, prove all references resolve.
        // On failure stage the untouched native action, followed by our cursor.
        // This includes unvisited later references: native still short-circuits.
        private int startCompound(TypedIRPreparedSteps.Prepared prepared) {
            var plan = prepared.compound();
            if (context.tracer() != null
                    || source.callback() != net.minecraft.commands.CommandResultCallback.EMPTY)
                return compoundNative(prepared.original());
            int capacity = CompoundScoreIR.MAX_PREDICATES * 2 + 2;
            if (compoundObjectives == null) {
                compoundObjectives = new Objective[capacity];
                compoundHolders = new ScoreHolder[capacity];
            }
            for (int i = 0; i < plan.objectives().size(); i++) {
                Objective value = scoreboard.getObjective(plan.objectives().get(i));
                if (value == null) return compoundNative(prepared.original());
                compoundObjectives[i] = value;
            }
            for (int i = 0; i < plan.slots().size(); i++) {
                var operand = plan.slots().get(i).operand();
                ScoreHolder holder = operand.self() ? source.getEntity() : operand.holder();
                if (holder == null) return compoundNative(prepared.original());
                compoundHolders[i] = holder;
            }
            if (compoundObjective(plan, plan.targetIndex()).getCriteria().isReadOnly())
                return compoundNative(prepared.original());
            current = prepared.original();
            currentPrepared = prepared;
            return DIRECT;
        }

        private int compoundNative(TypedScoreIR.Instruction instruction) {
            TypedScoreIR.compoundFallback();
            TypedScoreIR.fallback();
            // Unlike the old single-guard callback fallback, the original
            // compound BuildContexts still owns its native redirect chain.
            context.queueNext(new CommandQueueEntry<>(frame,
                    (execution, commandFrame) ->
                            instruction.vanilla().original().execute(source, execution, commandFrame)));
            if (nextIndex < instructions.length) {
                context.queueNext(new CommandQueueEntry<>(frame,
                        new QueuedTail(source, instructions, nextIndex)));
            }
            return STOP;
        }

        private Objective compoundObjective(CompoundScoreIR.Plan plan, int index) {
            return compoundObjectives[plan.slots().get(index).objectiveIndex()];
        }

        private ReadOnlyScoreInfo compoundRead(CompoundScoreIR.Plan plan, int index) {
            return scoreboard.getPlayerScoreInfo(compoundHolders[index], compoundObjective(plan, index));
        }

        // Each reached predicate has its own original modifier-stage debit.
        // No feedback, mutation, result callback or trace occurs between these
        // pure reads. The shared primitive is used by both backends.
        boolean compoundStage(int index) {
            if (quota() <= 0) return false;
            context.incrementCost();
            var plan = currentPrepared.compound();
            var stage = plan.stages().get(index);
            boolean pass;
            if (stage.evaluation() != CompoundScoreIR.Evaluation.READ) {
                pass = stage.evaluation() == CompoundScoreIR.Evaluation.KNOWN_PASS;
            } else {
                var predicate = stage.predicate();
                var left = compoundRead(plan, stage.leftIndex());
                boolean matched = false;
                if (left != null) {
                    if (predicate.range() != null) {
                        matched = predicate.range().matches(left.value());
                    } else {
                        int value = left.value();
                        if (stage.leftIndex() == stage.rightIndex()) {
                            TypedScoreIR.comparisonReadReused();
                            matched = ScoreConditionCommand.compareScores(value, value, predicate.comparison());
                        } else {
                            var right = compoundRead(plan, stage.rightIndex());
                            matched = right != null && ScoreConditionCommand.compareScores(
                                    value, right.value(), predicate.comparison());
                        }
                    }
                }
                pass = matched != predicate.unless();
            }
            TypedScoreIR.compoundStage(stage.evaluation() != CompoundScoreIR.Evaluation.READ, pass);
            if (!pass) TypedScoreIR.skippedConditional();
            return pass;
        }

        // Called only after all original predicate stages have passed.
        boolean compoundTerminal() {
            if (quota() <= 0) return false;
            context.incrementCost();
            var plan = currentPrepared.compound();
            objective = compoundObjective(plan, plan.targetIndex());
            targetResolved = compoundHolders[plan.targetIndex()];
            access = scoreboard.getOrCreatePlayerScore(targetResolved, objective);
            if (plan.sourceIndex() >= 0) {
                sourceObjective = compoundObjective(plan, plan.sourceIndex());
                sourceResolved = compoundHolders[plan.sourceIndex()];
                sourceAccess = scoreboard.getOrCreatePlayerScore(sourceResolved, sourceObjective);
            }
            TypedScoreIR.step(current);
            return true;
        }

        boolean completeCompound() {
            for (int i = 0; i < currentPrepared.compound().stages().size(); i++) {
                if (!compoundStage(i)) return false;
            }
            return compoundTerminal();
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
            // IR-037: binary shape and operand name were validated and
            // predecoded at compilation; the revision and score remain live.
            TypedIRPreparedSteps.Prepared prepared = currentPrepared;
            if (!TypedScoreIR.scoreCacheEnabled()
                    || prepared.binary() == null
                    || !(scoreboard instanceof ScoreValueRevisionAccess versions)) {
                return sourceAccess.get();
            }
            var key = new ScoreValueRevisionAccess.Key(
                    sourceResolved.getScoreboardName(),
                    prepared.operandObjective());
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
            TypedIRPreparedSteps.Prepared prepared = currentPrepared;
            TraceCallbacks tracer = context.tracer();
            try {
                int result;
                if (TypedScoreIR.singletonFeedbackEnabled()) {
                    // Preserve original single tracked-holder feedback,
                    // including distinct REMOVE/ADD/SET messages and
                    // the original (un-signed) source literal amount.
                    var holder = targetResolved;
                    var resolvedObjective = objective;
                    if (prepared.feedback() == TypedIRPreparedSteps.Feedback.OPERATION) {
                        var message = ScoreboardCommandAccessor
                                .functionCompiler$getScoreOperationResponse();
                        source.sendSuccess(() -> message.onSuccess().onSingle()
                                .create(holder, newScore, resolvedObjective), true);
                    } else {
                        var message = switch (prepared.feedback()) {
                            case ADD -> ScoreboardCommandAccessor.functionCompiler$getScoreAddResponse();
                            case REMOVE -> ScoreboardCommandAccessor.functionCompiler$getScoreRemoveResponse();
                            case SET -> ScoreboardCommandAccessor.functionCompiler$getScoreSetResponse();
                            case OPERATION -> throw new AssertionError("binary feedback in mutation");
                        };
                        source.sendSuccess(() -> message.onSuccess().onSingle()
                                .create(holder, newScore, resolvedObjective,
                                        prepared.feedbackAmount()), true);
                    }
                    result = newScore;
                    TypedScoreIR.singletonFeedbackUsed();
                } else {
                    CommandResponseTracker<net.minecraft.world.scores.ScoreHolder> response =
                            CommandResponseTracker.create();
                    response.track(targetResolved, newScore);
                    if (prepared.feedback() == TypedIRPreparedSteps.Feedback.OPERATION) {
                        result = response.sendFeedback(
                                source, true, ElementType.ANY,
                                ScoreboardCommandAccessor.functionCompiler$getScoreOperationResponse(),
                                objective
                        );
                    } else {
                        var message = switch (prepared.feedback()) {
                            case ADD -> ScoreboardCommandAccessor.functionCompiler$getScoreAddResponse();
                            case REMOVE -> ScoreboardCommandAccessor.functionCompiler$getScoreRemoveResponse();
                            case SET -> ScoreboardCommandAccessor.functionCompiler$getScoreSetResponse();
                            case OPERATION -> throw new AssertionError("binary feedback in mutation");
                        };
                        result = response.sendFeedback(
                                source, true, ElementType.ANY, message, objective,
                                prepared.feedbackAmount()
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
                currentPrepared = null;
                objective = null;
                access = null;
                sourceAccess = null;
                sourceObjective = null;
                targetResolved = null;
                sourceResolved = null;
            }
        }
    }
}
