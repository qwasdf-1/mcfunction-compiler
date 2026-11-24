package dev.functioncompiler;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * IR-036: conservative read/write, dynamic-holder and observable-boundary
 * analysis of the original per-command effects after canonicalization.
 *
 * This is NOT permission to reorder commands, fold writes or cache scoreboard
 * values: synchronous listeners, feedback, trace and queued callback work
 * remain observable even for disjoint score slots. An @s holder is dynamic
 * and conservatively aliases any literal holder when comparing commands.
 */
final class TypedIREffectAnalysis {
    private TypedIREffectAnalysis() {}

    record Boundary(int leftIndex, boolean slotDependency,
                    boolean dynamicHolderAlias, boolean observable) {
        Boundary {
            if (leftIndex < 0 || !observable) {
                throw new IllegalArgumentException("missing observable command barrier");
            }
        }

        boolean reorderPermitted() { return false; }
        boolean eliminateCommandPermitted() { return false; }
    }

    record Analysis(IR036CostModel.Features features, List<Boundary> boundaries) {
        Analysis {
            boundaries = List.copyOf(boundaries);
            if (boundaries.size() != features.blockedBoundaries()) {
                throw new IllegalArgumentException("lost original command boundary");
            }
            for (int i = 0; i < boundaries.size(); i++) {
                if (boundaries.get(i).leftIndex() != i
                        || !boundaries.get(i).observable()) {
                    throw new IllegalArgumentException("source boundary order changed");
                }
            }
        }
    }

    static Analysis analyze(TypedIROptimizer.Plan plan) {
        int guards = 0;
        int binaries = 0;
        int dynamics = 0;
        List<Boundary> boundaries = new ArrayList<>();
        List<TypedIROptimizer.Step> steps = plan.steps();
        for (int i = 0; i < steps.size(); i++) {
            TypedScoreIR.Instruction original = steps.get(i).original();
            TypedScoreIR.Instruction terminal =
                    original instanceof TypedScoreIR.Conditional condition
                            ? condition.terminal() : original;
            if (original instanceof TypedScoreIR.Conditional) guards++;
            if (terminal instanceof TypedScoreIR.Binary) binaries++;
            if (dynamic(original)) dynamics++;
            if (i == 0) continue;

            TypedScoreIR.Instruction previous = steps.get(i - 1).original();
            TypedScoreIR.Effects left = previous.effects();
            TypedScoreIR.Effects right = original.effects();
            if (!left.observableBoundary() || !right.observableBoundary()) {
                throw new IllegalArgumentException("unproven non-observable command");
            }
            boolean dynamicAlias = dynamic(previous) || dynamic(original);
            boolean conflict =
                    intersects(left.writes(), right.reads())
                    || intersects(left.writes(), right.writes())
                    || intersects(left.reads(), right.writes());
            boundaries.add(new Boundary(i - 1, conflict, dynamicAlias, true));
        }
        return new Analysis(new IR036CostModel.Features(
                steps.size(), guards, binaries, dynamics, boundaries.size()), boundaries);
    }

    private static boolean intersects(Set<TypedScoreIR.Slot> left,
                                      Set<TypedScoreIR.Slot> right) {
        if (left.isEmpty() || right.isEmpty()) return false;
        Set<TypedScoreIR.Slot> copy = new HashSet<>(left);
        copy.retainAll(right);
        return !copy.isEmpty();
    }

    private static boolean dynamic(TypedScoreIR.Instruction original) {
        TypedScoreIR.Instruction terminal =
                original instanceof TypedScoreIR.Conditional guard
                        ? guard.terminal() : original;
        if (original instanceof TypedScoreIR.Conditional guard
                && guard.conditionSelf()) return true;
        if (terminal.holderSelf()) return true;
        return terminal instanceof TypedScoreIR.Binary binary && binary.sourceSelf();
    }
}
