package dev.functioncompiler;

import net.minecraft.world.scores.ScoreHolder;

import java.util.Objects;

/**
 * COMPILER-IR-037: execution metadata specialization.
 *
 * Compile-time canonicalization produces exactly one immutable descriptor for
 * each ORIGINAL validated source command. The descriptor predecodes its shape,
 * target, optional guard, optional binary operand and original feedback kind.
 *
 * Runtime objective resolution remains fresh at EVERY source command boundary.
 * Only duplicate objective-name reads within the SAME source command, before
 * any scoreboard mutation/callback, may reuse the first result. Score accesses,
 * @s resolution, listeners, quota/trace/feedback and fallback remain live.
 * A conditional's original command is retained for quota and reentrant tails.
 */
final class TypedIRPreparedSteps {
    private TypedIRPreparedSteps() {}

    enum Feedback { ADD, REMOVE, SET, OPERATION }

    record Prepared(
            TypedScoreIR.Instruction original,
            TypedScoreIR.Conditional condition,
            TypedScoreIR.Binary binary,
            ScoreHolder targetHolder, boolean targetSelf, String targetObjective,
            ScoreHolder conditionHolder, boolean conditionSelf, String conditionObjective,
            ScoreHolder operandHolder, boolean operandSelf, String operandObjective,
            Feedback feedback, int feedbackAmount,
            boolean guardSharesTargetObjective,
            boolean operandSharesTargetObjective,
            boolean operandSharesGuardObjective,
            boolean comparisonSharesTargetObjective,
            boolean comparisonSharesGuardObjective,
            boolean operandSharesComparisonObjective,
            boolean comparisonSameSlot,
            CompoundScoreIR.Plan compound,
            GuardRunReuse.Shape guardRun
    ) {
        Prepared {
            Objects.requireNonNull(original);
            Objects.requireNonNull(targetObjective);
            Objects.requireNonNull(feedback);
            if ((original instanceof TypedScoreIR.Compound) != (compound != null))
                throw new IllegalArgumentException("invalid compound plan");
            if (!original.effects().observableBoundary()) {
                throw new IllegalArgumentException("lost original command effect boundary");
            }
            if (targetSelf == (targetHolder != null)) {
                throw new IllegalArgumentException("invalid target holder specialization");
            }
            if (condition == null) {
                if (conditionHolder != null || conditionSelf || conditionObjective != null) {
                    throw new IllegalArgumentException("unconditional step has guard fields");
                }
            } else {
                if (conditionSelf == (conditionHolder != null)
                        || conditionObjective == null || condition != original) {
                    throw new IllegalArgumentException("invalid condition specialization");
                }
            }
            if (guardSharesTargetObjective != (condition != null
                    && targetObjective.equals(conditionObjective))
                    || operandSharesTargetObjective != (binary != null
                    && targetObjective.equals(operandObjective))
                    || operandSharesGuardObjective != (condition != null && binary != null
                    && conditionObjective.equals(operandObjective))) {
                throw new IllegalArgumentException("unsound objective alias metadata");
            }
            boolean compares = condition != null && condition.comparison() != null;
            if (comparisonSharesTargetObjective != (compares
                    && targetObjective.equals(condition.comparisonObjective()))
                    || comparisonSharesGuardObjective != (compares
                    && conditionObjective.equals(condition.comparisonObjective()))
                    || operandSharesComparisonObjective != (compares && binary != null
                    && operandObjective.equals(condition.comparisonObjective()))
                    || comparisonSameSlot != (compares && samePredicateSlot(condition))) {
                throw new IllegalArgumentException("unsound comparison alias metadata");
            }
            if (binary == null) {
                if (operandHolder != null || operandSelf || operandObjective != null
                        || feedback == Feedback.OPERATION) {
                    throw new IllegalArgumentException("nonbinary step has operand fields");
                }
            } else if (operandSelf == (operandHolder != null)
                    || operandObjective == null || feedback != Feedback.OPERATION
                    || feedbackAmount != 0) {
                throw new IllegalArgumentException("invalid binary specialization");
            }
        }
    }

    static Prepared[] prepare(TypedIROptimizer.Plan plan) {
        Objects.requireNonNull(plan);
        Prepared[] result = new Prepared[plan.steps().size()];
        for (int i = 0; i < result.length; i++) {
            TypedScoreIR.Instruction original = plan.steps().get(i).original();
            if (original != plan.source().instructions().get(i)) {
                throw new IllegalArgumentException("optimizer changed original instruction identity");
            }
            GuardRunReuse.Shape shape = GuardRunReuse.shape(original);
            // Share identity only with the immediately preceding eligible
            // descriptor. Queued tails use the single-step overload (no run).
            if (shape != null && i > 0 && shape.equals(result[i-1].guardRun()))
                shape = result[i-1].guardRun();
            result[i] = prepare(original, shape);
        }
        return result;
    }

    /**
     * Single-step preparation is used ONLY by the exceptional queued
     * continuation. Hot interpreted and generated-bytecode executions use
     * descriptors allocated once at function compilation.
     */
    static Prepared prepare(TypedScoreIR.Instruction original) {
        return prepare(original, null);
    }

    private static Prepared prepare(TypedScoreIR.Instruction original, GuardRunReuse.Shape shape) {
        Objects.requireNonNull(original);
        TypedScoreIR.Conditional guard =
                original instanceof TypedScoreIR.Conditional condition ? condition : null;
        TypedScoreIR.Instruction terminal = guard != null ? guard.terminal()
                : original instanceof TypedScoreIR.Compound compound ? compound.terminal() : original;
        TypedScoreIR.Binary binary =
                terminal instanceof TypedScoreIR.Binary operation ? operation : null;
        TypedScoreIR.Mutation mutation =
                terminal instanceof TypedScoreIR.Mutation literal ? literal : null;
        if ((binary == null) == (mutation == null)) {
            throw new IllegalArgumentException("unrecognized typed terminal");
        }
        Feedback feedback;
        int amount;
        if (binary != null) {
            feedback = Feedback.OPERATION;
            amount = 0;
        } else {
            feedback = switch (mutation.operation()) {
                case ADD -> Feedback.ADD;
                case REMOVE -> Feedback.REMOVE;
                case SET -> Feedback.SET;
            };
            // Original amount, NOT the signed canonical REMOVE delta.
            amount = mutation.amount();
        }
        return new Prepared(original, guard, binary,
                original.holder(), original.holderSelf(), original.objective(),
                guard == null ? null : guard.conditionHolder(),
                guard != null && guard.conditionSelf(),
                guard == null ? null : guard.conditionObjective(),
                binary == null ? null : binary.sourceHolder(),
                binary != null && binary.sourceSelf(),
                binary == null ? null : binary.sourceObjective(),
                feedback, amount,
                guard != null && original.objective().equals(guard.conditionObjective()),
                binary != null && original.objective().equals(binary.sourceObjective()),
                guard != null && binary != null
                        && guard.conditionObjective().equals(binary.sourceObjective()),
                guard != null && guard.comparison() != null
                        && original.objective().equals(guard.comparisonObjective()),
                guard != null && guard.comparison() != null
                        && guard.conditionObjective().equals(guard.comparisonObjective()),
                guard != null && guard.comparison() != null && binary != null
                        && binary.sourceObjective().equals(guard.comparisonObjective()),
                guard != null && guard.comparison() != null && samePredicateSlot(guard),
                original instanceof TypedScoreIR.Compound compound ? CompoundScoreIR.prepare(compound) : null, shape);
    }
    /** Exact alias only: never assume an entity @s aliases a literal fake holder. */
    private static boolean samePredicateSlot(TypedScoreIR.Conditional guard) {
        return guard.conditionObjective().equals(guard.comparisonObjective())
                && guard.conditionSelf() == guard.comparisonSelf()
                && (guard.conditionSelf()
                    || guard.conditionHolder().getScoreboardName()
                        .equals(guard.comparisonHolder().getScoreboardName()));
    }

}
