package dev.functioncompiler;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * COMPILER-IR-035: explicit, immutable, effect-preserving optimization pass.
 *
 * This is a single-instruction canonicalization pass between validated typed
 * lowering and interpreter/JVM code generation. No command is elided, moved,
 * combined with another command or speculatively executed. Every source line
 * retains its exact original Instruction (including vanilla fallback and
 * feedback identity) and remains an observable effect/queue/quota boundary.
 *
 * The useful first transformation is to predecode the instruction dispatch
 * and canonicalize ADD/REMOVE literals to a single signed-delta opcode. The
 * original operation and unsigned argument remain in the original mutation
 * for its observable vanilla feedback. Binary operations likewise receive
 * an immutable opcode rather than runtime type inspection in the interpreter.
 */
final class TypedIROptimizer {
    private TypedIROptimizer() {}

    enum Op {
        ADD_LITERAL, SET_LITERAL,
        ASSIGN_SCORE, ADD_SCORE, SUBTRACT_SCORE, MULTIPLY_SCORE, MIN_SCORE, MAX_SCORE, DIVIDE_SCORE, MODULO_SCORE, SWAP_SCORE;

        boolean readsSourceScore() {
            return switch (this) {
                case ASSIGN_SCORE, ADD_SCORE, SUBTRACT_SCORE, MULTIPLY_SCORE, MIN_SCORE, MAX_SCORE, DIVIDE_SCORE, MODULO_SCORE, SWAP_SCORE -> true;
                case ADD_LITERAL, SET_LITERAL -> false;
            };
        }
    }

    record Step(TypedScoreIR.Instruction original, Op opcode, int literal) {
        Step {
            Objects.requireNonNull(original, "original source command");
            Objects.requireNonNull(opcode, "optimized opcode");
            if (!original.effects().observableBoundary()) {
                throw new IllegalArgumentException("cannot optimize through a command effect barrier");
            }
            TypedScoreIR.Instruction terminal =
                    original instanceof TypedScoreIR.Conditional guard
                            ? guard.terminal() : original instanceof TypedScoreIR.Compound compound
                                    ? compound.terminal() : original;
            if (terminal instanceof TypedScoreIR.Mutation mutation) {
                if (opcode.readsSourceScore()) {
                    throw new IllegalArgumentException("score opcode for literal mutation");
                }
                Op expected = mutation.operation() == ScoreAddCommand.Operation.SET
                        ? Op.SET_LITERAL : Op.ADD_LITERAL;
                int expectedLiteral = switch (mutation.operation()) {
                    case SET, ADD -> mutation.amount();
                    case REMOVE -> -mutation.amount(); // preserve JVM int overflow semantics
                };
                if (opcode != expected || literal != expectedLiteral) {
                    throw new IllegalArgumentException("mutation opcode/argument drift");
                }
            } else if (terminal instanceof TypedScoreIR.Binary binary) {
                Op expected = switch (binary.operation()) {
                    case ASSIGN -> Op.ASSIGN_SCORE;
                    case ADD -> Op.ADD_SCORE;
                    case SUBTRACT -> Op.SUBTRACT_SCORE;
                    case MULTIPLY -> Op.MULTIPLY_SCORE;
                    case MINIMUM -> Op.MIN_SCORE;
                    case MAXIMUM -> Op.MAX_SCORE;
                    case DIVIDE -> Op.DIVIDE_SCORE;
                    case MODULO -> Op.MODULO_SCORE;
                    case SWAP -> Op.SWAP_SCORE;
                };
                if (opcode != expected || literal != 0) {
                    throw new IllegalArgumentException("binary opcode/argument drift");
                }
            } else {
                throw new IllegalArgumentException("unsupported typed terminal");
            }
        }
    }

    record Plan(TypedScoreIR.Program source, List<Step> steps) {
        Plan {
            Objects.requireNonNull(source, "source program");
            steps = List.copyOf(steps);
            if (steps.size() != source.instructions().size()) {
                throw new IllegalArgumentException("source command count changed");
            }
            for (int i = 0; i < steps.size(); i++) {
                if (steps.get(i).original() != source.instructions().get(i)) {
                    throw new IllegalArgumentException("source command identity/order changed at " + i);
                }
            }
        }
    }

    static Plan optimize(TypedScoreIR.Program source) {
        Objects.requireNonNull(source);
        List<Step> output = new ArrayList<>(source.instructions().size());
        for (TypedScoreIR.Instruction original : source.instructions()) {
            output.add(classify(original));
        }
        return new Plan(source, output);
    }

    private static Step classify(TypedScoreIR.Instruction original) {
        TypedScoreIR.Instruction terminal =
                original instanceof TypedScoreIR.Conditional guard
                        ? guard.terminal() : original instanceof TypedScoreIR.Compound compound
                                ? compound.terminal() : original;
        if (terminal instanceof TypedScoreIR.Mutation mutation) {
            return switch (mutation.operation()) {
                case ADD -> new Step(original, Op.ADD_LITERAL, mutation.amount());
                case REMOVE -> new Step(original, Op.ADD_LITERAL, -mutation.amount());
                case SET -> new Step(original, Op.SET_LITERAL, mutation.amount());
            };
        }
        if (terminal instanceof TypedScoreIR.Binary binary) {
            Op opcode = switch (binary.operation()) {
                case ASSIGN -> Op.ASSIGN_SCORE;
                case ADD -> Op.ADD_SCORE;
                case SUBTRACT -> Op.SUBTRACT_SCORE;
                case MULTIPLY -> Op.MULTIPLY_SCORE;
                    case MINIMUM -> Op.MIN_SCORE;
                    case MAXIMUM -> Op.MAX_SCORE;
                    case DIVIDE -> Op.DIVIDE_SCORE;
                    case MODULO -> Op.MODULO_SCORE;
                    case SWAP -> Op.SWAP_SCORE;
            };
            return new Step(original, opcode, 0);
        }
        throw new IllegalArgumentException("unsupported typed IR instruction");
    }
}
