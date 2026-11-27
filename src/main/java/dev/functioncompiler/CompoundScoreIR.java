package dev.functioncompiler;

import net.minecraft.advancements.predicates.MinMaxBounds;
import net.minecraft.world.scores.ScoreHolder;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.HashSet;

/**
 * IR-039: ordered, short-circuit predicate stages over one original command.
 * A stage may reuse an earlier successful raw predicate, but its quota debit
 * and branch remain. Nothing is reused across source-command boundaries.
 */
final class CompoundScoreIR {
    private CompoundScoreIR() {}
    static final int MAX_PREDICATES = 8;
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_COMPOUND_SCORE"));
    static boolean enabled() { return ENABLED && TypedScoreIR.extendedScoreEnabled(); }
    private static final boolean DATAFLOW =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DATAFLOW"));
    static boolean dataflowEnabledFor(net.minecraft.resources.Identifier id) {
        // Only the explicitly enabled benchmark has an identical IR-039 twin.
        return DATAFLOW && !(Boolean.parseBoolean(System.getenv("FC_TYPED_IR040_BENCHMARK"))
                && id.getNamespace().equals("fc_ir") && (id.getPath().equals("ir017_ir040_perf_base")
                        || (Boolean.parseBoolean(System.getenv("FC_TYPED_IR041_BENCHMARK"))
                            && id.getPath().equals("ir017_ir041_mixed_base"))
                        || (Boolean.parseBoolean(System.getenv("FC_TYPED_IR042_BENCHMARK"))
                            && id.getPath().equals("ir017_ir042_interp"))));
    }
    static int comparisonMask(ScoreConditionCommand.Operator operator) {
        return switch (operator) {
            case LESS_THAN -> PredicateFacts.LT;
            case LESS_THAN_OR_EQUAL -> PredicateFacts.LT | PredicateFacts.EQ;
            case EQUALS -> PredicateFacts.EQ;
            case GREATER_THAN -> PredicateFacts.GT;
            case GREATER_THAN_OR_EQUAL -> PredicateFacts.GT | PredicateFacts.EQ;
        };
    }

    record Operand(ScoreHolder holder, boolean self, String objective) {
        Operand {
            Objects.requireNonNull(objective);
            if (self == (holder != null)) throw new IllegalArgumentException("ambiguous operand");
        }
        TypedScoreIR.Slot key() {
            return new TypedScoreIR.Slot(TypedScoreIR.slotName(holder, self), objective);
        }
    }

    record Predicate(Operand left, MinMaxBounds.Ints range, String rangeText,
                     ScoreConditionCommand.Operator comparison, Operand right, boolean unless) {
        Predicate {
            Objects.requireNonNull(left);
            if ((range == null) == (comparison == null)
                    || (range == null) != (rangeText == null)
                    || (comparison == null) != (right == null))
                throw new IllegalArgumentException("invalid predicate shape");
        }
        RawKey rawKey() {
            return new RawKey(left.key(), rangeText, comparison, right == null ? null : right.key());
        }
    }
    private record RawKey(TypedScoreIR.Slot left, String range,
                          ScoreConditionCommand.Operator comparison, TypedScoreIR.Slot right) {}
    record Slot(Operand operand, int objectiveIndex) {}
    enum Evaluation { READ, KNOWN_PASS, KNOWN_FAIL }
    record Stage(Predicate predicate, int leftIndex, int rightIndex, Evaluation evaluation,
                 boolean dataflowProven) {}
    record Plan(List<String> objectives, List<Slot> slots, List<Stage> stages,
                int targetIndex, int sourceIndex, boolean dataflow) {
        Plan {
            objectives = List.copyOf(objectives);
            slots = List.copyOf(slots);
            stages = List.copyOf(stages);
        }
    }

    static Plan prepare(TypedScoreIR.Compound instruction) {
        var terminal = instruction.terminal();
        return preparePredicates(instruction.predicates(), instruction.dataflow(),
                new Operand(terminal.holder(), terminal.holderSelf(), terminal.objective()),
                terminal instanceof TypedScoreIR.Binary binary
                        ? new Operand(binary.sourceHolder(), binary.sourceSelf(), binary.sourceObjective()) : null);
    }

    static Plan preparePredicates(List<Predicate> predicates, boolean dataflow,
                                  Operand targetOperand, Operand sourceOperand) {
        Map<String, Integer> objectives = new LinkedHashMap<>();
        Map<TypedScoreIR.Slot, Integer> indices = new LinkedHashMap<>();
        List<Slot> slots = new ArrayList<>();
        List<Stage> stages = new ArrayList<>();
        Map<RawKey, Boolean> passed = new LinkedHashMap<>();
        PredicateFacts.Flow flow = dataflow ? new PredicateFacts.Flow() : null;
        for (Predicate p : predicates) {
            int left = add(p.left(), objectives, indices, slots);
            int right = p.right() == null ? -1 : add(p.right(), objectives, indices, slots);
            // Reaching this stage proves every preceding stage passed.
            // Exact source keys include polarity-independent parsed range text,
            // operand identity, and operator; @s never aliases a literal key.
            Boolean priorUnless = passed.get(p.rawKey());
            Evaluation evaluation = priorUnless == null ? Evaluation.READ
                    : priorUnless == p.unless() ? Evaluation.KNOWN_PASS : Evaluation.KNOWN_FAIL;
            boolean dataflowProven = false;
            if (flow != null) {
                var inferred = p.range() != null
                        ? flow.range(left, p.rangeText(), p.unless())
                        : flow.comparison(left, right, comparisonMask(p.comparison()), p.unless());
                if (evaluation == Evaluation.READ) {
                    dataflowProven = inferred != PredicateFacts.Outcome.UNKNOWN;
                    evaluation = switch (inferred) {
                        case UNKNOWN -> Evaluation.READ;
                        case PASS -> Evaluation.KNOWN_PASS;
                        case FAIL -> Evaluation.KNOWN_FAIL;
                    };
                }
            }
            stages.add(new Stage(p, left, right, evaluation, dataflowProven));
            passed.putIfAbsent(p.rawKey(), p.unless());
        }
        int target = targetOperand == null ? -1 : add(targetOperand, objectives, indices, slots);
        int source = sourceOperand == null ? -1 : add(sourceOperand, objectives, indices, slots);
        return new Plan(new ArrayList<>(objectives.keySet()), slots, stages, target, source, dataflow);
    }

    private static int add(Operand operand, Map<String, Integer> objectives,
                           Map<TypedScoreIR.Slot, Integer> indices, List<Slot> slots) {
        Integer existing = indices.get(operand.key());
        if (existing != null) return existing;
        int objective = objectives.computeIfAbsent(operand.objective(), k -> objectives.size());
        int index = slots.size();
        slots.add(new Slot(operand, objective));
        indices.put(operand.key(), index);
        return index;
    }

    static Set<TypedScoreIR.Slot> reads(List<Predicate> predicates) {
        Set<TypedScoreIR.Slot> reads = new HashSet<>();
        for (Predicate p : predicates) {
            reads.add(p.left().key());
            if (p.right() != null) reads.add(p.right().key());
        }
        return reads;
    }
}
