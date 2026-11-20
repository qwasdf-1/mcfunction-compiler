package dev.functioncompiler;

import net.minecraft.advancements.predicates.MinMaxBounds;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;
import net.minecraft.world.scores.ScoreAccess;
import net.minecraft.world.scores.ScoreHolder;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.atomic.LongAdder;

/**
 * COMPILER-IR-008/009. Post-Brigadier typed semantic IR.
 *
 * All instructions originate from previously validated vanilla commands,
 * not text reparsing. String checks in each adapter restrict accepted shapes.
 * We retain every original command as a precise fallback and treat each
 * command result/feedback as an observable effect barrier: no scoreboard
 * value is cached or elided across instruction boundaries.
 *
 * Two independent backends consume this same immutable IR: a reference
 * interpreter and real ASM direct operations. Both retain vanilla function
 * scheduling, result propagation, quota debits and trace callback boundaries.
 */
final class TypedScoreIR {
    private static final String MODE = System.getenv("FC_TYPED_IR_MODE");
    private static final String NAMESPACE = System.getenv("FC_TYPED_IR_NAMESPACE");
    private static final boolean ACTIVE = ("interpreted".equals(MODE) || "bytecode".equals(MODE))
            && NAMESPACE != null && !NAMESPACE.isBlank();
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static final int MAX_REGION_LENGTH = 64;
    private static final LongAdder COMPILED_REGIONS = new LongAdder();
    private static final LongAdder BYTECODE_REGIONS = new LongAdder();
    private static final LongAdder EXECUTED_REGIONS = new LongAdder();
    private static final LongAdder EXECUTED_STEPS = new LongAdder();
    private static final LongAdder FALLBACK_STEPS = new LongAdder();
    private static final LongAdder BINARY_STEPS = new LongAdder();
    private static final LongAdder CONDITIONAL_STEPS = new LongAdder();
    private static final LongAdder CONDITIONAL_SKIPS = new LongAdder();

    private TypedScoreIR() {}

    static boolean enabledFor(Identifier id) {
        return ACTIVE && id != null && NAMESPACE.equals(id.getNamespace())
                && !ProbeConfiguration.isNamespaceExcluded(id.getNamespace());
    }

    /** Abstract scoreboard location; a namespace-local type, not a cached score. */
    record Slot(String holderName, String objectiveName) {
        Slot {
            Objects.requireNonNull(holderName);
            Objects.requireNonNull(objectiveName);
        }
    }

    /**
     * Conservative effect summary. Reads and writes describe the scoreboard
     * locations; feedback, tracing, and potential scoreboard listeners make
     * EACH command an observable barrier even if two slots do not overlap.
     * In particular, does not authorize forwarding a cached value to the next
     * command. This explicitly prevents unsound common-subexpression removal.
     */
    record Effects(Set<Slot> reads, Set<Slot> writes, boolean observableBoundary) {
        Effects {
            reads = Set.copyOf(reads);
            writes = Set.copyOf(writes);
        }

        boolean mayReuseValueAcross(Effects next) {
            // Returning false is deliberate: any per-command result callback
            // may mutate even unrelated scoreboard slots via another mod.
            return !observableBoundary && !next.observableBoundary
                    && reads.stream().noneMatch(next.writes::contains)
                    && writes.stream().noneMatch(next.reads::contains)
                    && writes.stream().noneMatch(next.writes::contains);
        }
    }

    sealed interface Instruction permits Mutation, Binary, Conditional {
        FusedRegionPrototype.FusedCommand vanilla();
        ScoreHolder holder();
        String objective();
        Effects effects();
    }

    record Mutation(
            FusedRegionPrototype.FusedCommand vanilla,
            ScoreHolder holder,
            String objective,
            ScoreAddCommand.Operation operation,
            int amount
    ) implements Instruction {
        Mutation {
            Objects.requireNonNull(vanilla);
            Objects.requireNonNull(holder);
            Objects.requireNonNull(objective);
            Objects.requireNonNull(operation);
        }
        @Override
        public Effects effects() {
            Slot target = new Slot(holder.getScoreboardName(), objective);
            return new Effects(
                    operation == ScoreAddCommand.Operation.SET ? Set.of() : Set.of(target),
                    Set.of(target), true);
        }
    }

    /** Only =, +=, -=, *=; no divide-by-zero, swap or multi-write operations. */
    enum BinaryOperator { ASSIGN, ADD, SUBTRACT, MULTIPLY }

    record Binary(
            FusedRegionPrototype.FusedCommand vanilla,
            ScoreHolder holder,
            String objective,
            BinaryOperator operation,
            ScoreHolder sourceHolder,
            String sourceObjective
    ) implements Instruction {
        Binary {
            Objects.requireNonNull(vanilla);
            Objects.requireNonNull(holder);
            Objects.requireNonNull(objective);
            Objects.requireNonNull(operation);
            Objects.requireNonNull(sourceHolder);
            Objects.requireNonNull(sourceObjective);
        }
        @Override
        public Effects effects() {
            Slot target = new Slot(holder.getScoreboardName(), objective);
            Slot source = new Slot(sourceHolder.getScoreboardName(), sourceObjective);
            Set<Slot> reads = new HashSet<>();
            reads.add(source);
            if (operation != BinaryOperator.ASSIGN) reads.add(target);
            return new Effects(reads, Set.of(target), true);
        }
    }

    /**
     * Direct-lowered conditional mutation. Only a single vanilla-validated
     * literal score-matches condition is accepted. The runtime checks the
     * guard BEFORE modifying the target score and charges its modifier-stage
     * quota debit only on passing guards, as the existing fused callback does.
     */
    record Conditional(
            FusedRegionPrototype.FusedCommand vanilla,
            Mutation mutation,
            ScoreHolder conditionHolder,
            String conditionObjective,
            MinMaxBounds.Ints range,
            boolean unless
    ) implements Instruction {
        Conditional {
            Objects.requireNonNull(vanilla);
            Objects.requireNonNull(mutation);
            Objects.requireNonNull(conditionHolder);
            Objects.requireNonNull(conditionObjective);
            Objects.requireNonNull(range);
        }
        @Override
        public ScoreHolder holder() { return mutation.holder(); }
        @Override
        public String objective() { return mutation.objective(); }
        @Override
        public Effects effects() {
            Effects inner = mutation.effects();
            HashSet<Slot> reads = new HashSet<>(inner.reads());
            reads.add(new Slot(conditionHolder.getScoreboardName(), conditionObjective));
            return new Effects(reads, inner.writes(), true);
        }
    }

    record Program(List<Instruction> instructions) {
        Program {
            instructions = List.copyOf(instructions);
            if (instructions.size() < 2 || instructions.size() > MAX_REGION_LENGTH) {
                throw new IllegalArgumentException("typed IR region length outside [2,64]");
            }
            // Fail closed if future instruction families forget to implement
            // their effect model (critical for the next optimizer stage).
            for (Instruction instruction : instructions) {
                if (!instruction.effects().observableBoundary()) {
                    throw new IllegalArgumentException("unproven unobservable IR instruction");
                }
            }
        }
    }

    static InstantiatedFunction<CommandSourceStack> compile(
            PlainTextFunction<CommandSourceStack> original
    ) {
        List<UnboundEntryAction<CommandSourceStack>> result = new ArrayList<>();
        List<Instruction> pending = new ArrayList<>();
        boolean changed = false;
        for (UnboundEntryAction<CommandSourceStack> entry : original.entries()) {
            Instruction instruction = lower(entry);
            if (instruction == null) {
                changed |= flush(result, pending);
                result.add(entry);  // Unknown command retains its vanilla queue position.
                continue;
            }
            if (pending.size() == MAX_REGION_LENGTH) changed |= flush(result, pending);
            pending.add(instruction);
        }
        changed |= flush(result, pending);
        return changed ? new CompiledFunction(original, List.copyOf(result)) : original;
    }

    private static Instruction lower(UnboundEntryAction<CommandSourceStack> entry) {
        FusedRegionPrototype.FusedCommand parsed = FusedRegionPrototype.fusedCommand(entry);
        if (parsed == null) return null;
        var command = parsed.command().getTopContext().getCommand();
        if (command instanceof ScoreAddCommand mutation) return mutation.toTypedIR(parsed);
        if (command instanceof ScoreOperationCommand binary) return binary.toTypedIR(parsed);
        if (command instanceof ScoreConditionCommand condition) return condition.toTypedIR(parsed);
        return null;
    }

    private static boolean flush(
            List<UnboundEntryAction<CommandSourceStack>> result,
            List<Instruction> pending
    ) {
        if (pending.isEmpty()) return false;
        if (pending.size() == 1) {
            result.add(pending.getFirst().vanilla().original());
            pending.clear();
            return false;
        }
        Program program = new Program(pending);
        UnboundEntryAction<CommandSourceStack> action = new Interpreted(program);
        if ("bytecode".equals(MODE)) {
            try {
                if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_FORCE_FAILURE"))) {
                    throw new IllegalStateException("IR injected compilation failure");
                }
                action = TypedScoreIRBytecode.emit(program);
                if (DIAGNOSTICS) BYTECODE_REGIONS.increment();
            } catch (RuntimeException | LinkageError compileError) {
                FunctionCompilerMod.LOGGER.warn("Typed IR bytecode fallback: {}",
                        compileError.toString());
            }
        }
        result.add(action);
        if (DIAGNOSTICS) COMPILED_REGIONS.increment();
        pending.clear();
        return true;
    }

    static boolean retainsOriginal(
            InstantiatedFunction<?> compiled,
            InstantiatedFunction<?> original
    ) {
        return compiled instanceof CompiledFunction typed && typed.original() == original;
    }

    static void executed() {
        if (DIAGNOSTICS) EXECUTED_REGIONS.increment();
    }

    static void step(Instruction instruction) {
        if (!DIAGNOSTICS) return;
        EXECUTED_STEPS.increment();
        if (instruction instanceof Binary) BINARY_STEPS.increment();
        if (instruction instanceof Conditional) CONDITIONAL_STEPS.increment();
    }

    static void skippedConditional() {
        if (DIAGNOSTICS) CONDITIONAL_SKIPS.increment();
    }

    static void fallback() {
        if (DIAGNOSTICS) FALLBACK_STEPS.increment();
    }

    static int report(CommandSourceStack source) {
        source.sendSuccess(() -> net.minecraft.network.chat.Component.literal(
                diagnosticStatus()), false);
        return 1;
    }

    static String diagnosticStatus() {
        if (!ACTIVE) return "IR008 disabled";
        return "IR008 mode=" + MODE + " namespace=" + NAMESPACE
                + " compiled_regions=" + COMPILED_REGIONS.sum()
                + " bytecode_regions=" + BYTECODE_REGIONS.sum()
                + " executed_regions=" + EXECUTED_REGIONS.sum()
                + " executed_steps=" + EXECUTED_STEPS.sum()
                + " fallback_steps=" + FALLBACK_STEPS.sum()
                + " binary_steps=" + BINARY_STEPS.sum()
                + " conditional_steps=" + CONDITIONAL_STEPS.sum()
                + " conditional_skips=" + CONDITIONAL_SKIPS.sum();
    }

    private record CompiledFunction(
            PlainTextFunction<CommandSourceStack> original,
            List<UnboundEntryAction<CommandSourceStack>> entries
    ) implements InstantiatedFunction<CommandSourceStack> {
        @Override
        public Identifier id() { return original.id(); }
    }

    static final class Interpreted implements UnboundEntryAction<CommandSourceStack> {
        private final Program program;

        Interpreted(Program program) { this.program = program; }

        @Override
        public void execute(
                CommandSourceStack source,
                ExecutionContext<CommandSourceStack> context,
                Frame frame
        ) {
            TypedScoreIRRuntime.State state =
                    new TypedScoreIRRuntime.State(source, context, frame);
            executed();
            for (Instruction instruction : program.instructions()) {
                int decision = state.begin(instruction);
                if (decision == TypedScoreIRRuntime.STOP) return;
                if (decision != TypedScoreIRRuntime.DIRECT) continue;
                ScoreAccess score = state.access();
                int updated;
                if (instruction instanceof Binary binary) {
                    int operand = state.sourceAccess().get();
                    updated = switch (binary.operation()) {
                        case ASSIGN -> { score.set(operand); yield operand; }
                        case ADD -> score.add(operand);
                        case SUBTRACT -> score.add(-operand);
                        case MULTIPLY -> {
                            int value = score.get() * operand;
                            score.set(value);
                            yield value;
                        }
                    };
                } else {
                    Mutation mutation = instruction instanceof Conditional condition
                            ? condition.mutation()
                            : (Mutation) instruction;
                    updated = switch (mutation.operation()) {
                        case ADD -> score.add(mutation.amount());
                        case REMOVE -> score.add(-mutation.amount());
                        case SET -> {
                            score.set(mutation.amount());
                            yield mutation.amount();
                        }
                    };
                }
                state.finish(updated);
            }
        }
    }
}
