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
 * Runtime objective/score lookups, @s resolution, scoreboard listeners,
 * quota/trace/feedback and vanilla fallback are NEVER hoisted or omitted.
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
            Feedback feedback, int feedbackAmount
    ) {
        Prepared {
            Objects.requireNonNull(original);
            Objects.requireNonNull(targetObjective);
            Objects.requireNonNull(feedback);
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
            result[i] = prepare(original);
        }
        return result;
    }

    /**
     * Single-step preparation is used ONLY by the exceptional queued
     * continuation. Hot interpreted and generated-bytecode executions use
     * descriptors allocated once at function compilation.
     */
    static Prepared prepare(TypedScoreIR.Instruction original) {
        Objects.requireNonNull(original);
        TypedScoreIR.Conditional guard =
                original instanceof TypedScoreIR.Conditional condition ? condition : null;
        TypedScoreIR.Instruction terminal = guard == null ? original : guard.terminal();
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
                feedback, amount);
    }
}
