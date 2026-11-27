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
public final class TypedScoreIR {
    private static final String MODE = TypedCompilerConfiguration.mode();
    private static final String NAMESPACE = System.getenv("FC_TYPED_IR_NAMESPACE");
    // Optional exact function boundary for original-publisher real-world pilots.
    // Empty/unset retains the existing namespace-wide typed compiler contract.
    private static final String FUNCTION_FILTER =
            System.getenv("FC_TYPED_IR_FUNCTION_FILTER");
    // Explicit bounded list for publisher admission diagnostics; a single exact
    // ID retains the previous filter behavior. No glob or namespace expansion.
    private static final java.util.Set<String> FUNCTION_FILTER_IDS =
            FUNCTION_FILTER == null || FUNCTION_FILTER.isEmpty() ? java.util.Set.of()
                    : java.util.Set.copyOf(java.util.Arrays.asList(FUNCTION_FILTER.split(",", -1)));
    private static final boolean ACTIVE = ("interpreted".equals(MODE) || "bytecode".equals(MODE))
            && NAMESPACE != null && !NAMESPACE.isBlank();
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    // IR-018: dynamic @s scoreboard holder lowering is research-only and
    // independently gated from IR-017 ranged-condition syntax.
    private static final boolean SELF_HOLDER =
            TypedCompilerConfiguration.flag("FC_TYPED_IR_SELF_HOLDER");
    static boolean selfHolderEnabled() { return SELF_HOLDER; }
    static String slotName(ScoreHolder holder, boolean isSelf) {
        return isSelf ? "@s" : holder.getScoreboardName();
    }
    // IR-011: lower the exact one-element scoreboard feedback case without
    // allocating a general CommandResponseTracker. No production default.
    private static final boolean SINGLETON_FEEDBACK =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SINGLETON_FEEDBACK"));
    private static volatile boolean singletonFeedbackRuntime = SINGLETON_FEEDBACK;
    static final int MAX_REGION_LENGTH = 64;
    private static final LongAdder COMPILED_REGIONS = new LongAdder();
    private static final LongAdder BYTECODE_REGIONS = new LongAdder();
    private static final LongAdder EXECUTED_REGIONS = new LongAdder();
    private static final LongAdder EXECUTED_STEPS = new LongAdder();
    private static final LongAdder FALLBACK_STEPS = new LongAdder();
    private static final LongAdder BINARY_STEPS = new LongAdder();
    private static final LongAdder CONDITIONAL_STEPS = new LongAdder();
    private static final LongAdder GUARDED_BINARY_STEPS = new LongAdder();
    private static final LongAdder CONDITIONAL_SKIPS = new LongAdder();
    private static final LongAdder SINGLETON_FEEDBACK_STEPS = new LongAdder();
    private static final LongAdder TRACKER_FEEDBACK_STEPS = new LongAdder();
    private static final LongAdder REENTRANT_YIELDS = new LongAdder();
    private static final LongAdder REENTRANT_QUEUED_STEPS = new LongAdder();
    // IR-037: counts actual same-command map lookups removed (DIAGNOSTICS only).
    private static final LongAdder OBJECTIVE_LOOKUPS_REUSED = new LongAdder();
    private static final LongAdder COMPARISON_EVALUATIONS = new LongAdder();
    private static final LongAdder COMPARISON_READS_REUSED = new LongAdder();
    private static final LongAdder MINMAX_STEPS = new LongAdder();
    private static final LongAdder COMPOUND_STAGES = new LongAdder();
    private static final LongAdder COMPOUND_REUSED = new LongAdder();
    private static final LongAdder COMPOUND_SHORT_CIRCUITS = new LongAdder();
    private static final LongAdder COMPOUND_FALLBACKS = new LongAdder();
    private static final LongAdder COMPOUND_EMPTY_STAGES = new LongAdder();
    private static final LongAdder DATAFLOW_PROOFS = new LongAdder();
    private static final LongAdder DATAFLOW_READS_REUSED = new LongAdder();
    private static final LongAdder NATIVE_ARITHMETIC_STEPS = new LongAdder();
    private static final LongAdder NATIVE_ARITHMETIC_ERRORS = new LongAdder();

    private TypedScoreIR() {}

    static boolean enabledFor(Identifier id) {
        return ACTIVE && id != null && NAMESPACE.equals(id.getNamespace())
                && !ProbeConfiguration.isNamespaceExcluded(id.getNamespace())
                && (FUNCTION_FILTER_IDS.isEmpty() || FUNCTION_FILTER_IDS.contains(id.toString()));
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

    sealed interface Instruction permits Mutation, Binary, Conditional, Compound {
        FusedRegionPrototype.FusedCommand vanilla();
        ScoreHolder holder();
        default boolean holderSelf() { return false; }
        String objective();
        Effects effects();
    }

    record Mutation(
            FusedRegionPrototype.FusedCommand vanilla,
            ScoreHolder holder,
            boolean holderSelf,
            String objective,
            ScoreAddCommand.Operation operation,
            int amount
    ) implements Instruction {
        Mutation {
            Objects.requireNonNull(vanilla);
            if (!holderSelf) Objects.requireNonNull(holder);
            if (holderSelf && holder != null) throw new IllegalArgumentException("ambiguous holder");
            Objects.requireNonNull(objective);
            Objects.requireNonNull(operation);
        }
        @Override
        public Effects effects() {
            Slot target = new Slot(slotName(holder, holderSelf), objective);
            return new Effects(
                    operation == ScoreAddCommand.Operation.SET ? Set.of() : Set.of(target),
                    Set.of(target), true);
        }
    }

    // IR-038: extended non-throwing, single-write score operations and comparisons.
    private static final boolean EXTENDED_SCORE =
            TypedCompilerConfiguration.flag("FC_TYPED_IR_EXTENDED_SCORE");
    static boolean extendedScoreEnabled() { return EXTENDED_SCORE; }

    /** Single-write operators; division, modulo and swap remain native. */
    enum BinaryOperator {
        ASSIGN, ADD, SUBTRACT, MULTIPLY, MINIMUM, MAXIMUM, DIVIDE, MODULO, SWAP;
        boolean nativeArithmetic() { return this == DIVIDE || this == MODULO || this == SWAP; }
    }

    record Binary(
            FusedRegionPrototype.FusedCommand vanilla,
            ScoreHolder holder,
            boolean holderSelf,
            String objective,
            BinaryOperator operation,
            ScoreHolder sourceHolder,
            boolean sourceSelf,
            String sourceObjective,
            net.minecraft.commands.arguments.OperationArgument.Operation nativeOperation
    ) implements Instruction {
        Binary(FusedRegionPrototype.FusedCommand vanilla, ScoreHolder holder, boolean holderSelf,
               String objective, BinaryOperator operation, ScoreHolder sourceHolder,
               boolean sourceSelf, String sourceObjective) {
            this(vanilla, holder, holderSelf, objective, operation, sourceHolder, sourceSelf,
                    sourceObjective, null);
        }
        Binary {
            Objects.requireNonNull(vanilla);
            if (!holderSelf) Objects.requireNonNull(holder);
            if (holderSelf && holder != null) throw new IllegalArgumentException("ambiguous target");
            Objects.requireNonNull(objective);
            Objects.requireNonNull(operation);
            if (!sourceSelf) Objects.requireNonNull(sourceHolder);
            if (sourceSelf && sourceHolder != null) throw new IllegalArgumentException("ambiguous source");
            Objects.requireNonNull(sourceObjective);
            if (operation.nativeArithmetic() != (nativeOperation != null))
                throw new IllegalArgumentException("native arithmetic operand mismatch");
        }
        @Override
        public Effects effects() {
            Slot target = new Slot(slotName(holder, holderSelf), objective);
            Slot source = new Slot(slotName(sourceHolder, sourceSelf), sourceObjective);
            Set<Slot> reads = new HashSet<>();
            reads.add(source);
            if (operation != BinaryOperator.ASSIGN) reads.add(target);
            Set<Slot> writes = new HashSet<>();
            writes.add(target);
            if (operation == BinaryOperator.SWAP) writes.add(source);
            return new Effects(reads, writes, true);
        }
    }

    /**
     * IR-017: one parsed inclusive score range, guarding either a scoreboard
     * mutation or a safe scoreboard binary operation. The predicate and its
     * already-validated terminal are both represented in one IR instruction,
     * so no result, quota or queue boundary can be lost during emission.
     */
    record Conditional(
            FusedRegionPrototype.FusedCommand vanilla,
            Instruction terminal,
            ScoreHolder conditionHolder,
            boolean conditionSelf,
            String conditionObjective,
            MinMaxBounds.Ints range,
            boolean unless,
            ScoreConditionCommand.Operator comparison,
            ScoreHolder comparisonHolder,
            boolean comparisonSelf,
            String comparisonObjective
    ) implements Instruction {
        Conditional(FusedRegionPrototype.FusedCommand vanilla, Instruction terminal,
                    ScoreHolder conditionHolder, boolean conditionSelf,
                    String conditionObjective, MinMaxBounds.Ints range, boolean unless) {
            this(vanilla, terminal, conditionHolder, conditionSelf, conditionObjective,
                    range, unless, null, null, false, null);
        }

        Conditional {
            Objects.requireNonNull(vanilla);
            Objects.requireNonNull(terminal);
            if (!(terminal instanceof Mutation || terminal instanceof Binary)) {
                throw new IllegalArgumentException("conditional terminal must be mutation or binary");
            }
            if (!conditionSelf) Objects.requireNonNull(conditionHolder);
            if (conditionSelf && conditionHolder != null) throw new IllegalArgumentException("ambiguous guard");
            Objects.requireNonNull(conditionObjective);
            if ((range == null) == (comparison == null)) {
                throw new IllegalArgumentException("exactly one predicate kind required");
            }
            if (comparison == null) {
                if (comparisonHolder != null || comparisonSelf || comparisonObjective != null) {
                    throw new IllegalArgumentException("range with comparison fields");
                }
            } else {
                if (comparisonSelf == (comparisonHolder != null)) {
                    throw new IllegalArgumentException("ambiguous comparison holder");
                }
                Objects.requireNonNull(comparisonObjective);
            }
        }
        @Override
        public ScoreHolder holder() { return terminal.holder(); }
        @Override
        public boolean holderSelf() { return terminal.holderSelf(); }
        @Override
        public String objective() { return terminal.objective(); }
        @Override
        public Effects effects() {
            Effects inner = terminal.effects();
            HashSet<Slot> reads = new HashSet<>(inner.reads());
            reads.add(new Slot(slotName(conditionHolder, conditionSelf), conditionObjective));
            if (comparison != null) {
                reads.add(new Slot(slotName(comparisonHolder, comparisonSelf), comparisonObjective));
            }
            return new Effects(reads, inner.writes(), true);
        }
    }

    /** Ordered AND of individually observable quota/short-circuit stages.
     * The parent source command remains one queue/feedback boundary. */
    record Compound(FusedRegionPrototype.FusedCommand vanilla,
                    Instruction terminal,
                    List<CompoundScoreIR.Predicate> predicates,
                    boolean dataflow) implements Instruction {
        Compound {
            Objects.requireNonNull(vanilla);
            Objects.requireNonNull(terminal);
            predicates = List.copyOf(predicates);
            if (!(terminal instanceof Mutation || terminal instanceof Binary)
                    || terminal.vanilla() != vanilla || predicates.size() < 2
                    || predicates.size() > CompoundScoreIR.MAX_PREDICATES) {
                throw new IllegalArgumentException("invalid compound source command");
            }
        }
        @Override public ScoreHolder holder() { return terminal.holder(); }
        @Override public boolean holderSelf() { return terminal.holderSelf(); }
        @Override public String objective() { return terminal.objective(); }
        @Override public Effects effects() {
            Effects inner = terminal.effects();
            Set<Slot> reads = new HashSet<>(inner.reads());
            reads.addAll(CompoundScoreIR.reads(predicates));
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

    /**
     * IR-016: MixedFunctionIR now owns the ordered source-to-program lowering.
     * The runtime gets executable entries from that immutable representation,
     * not an independently flattened mutable list. Opaque originals always
     * retain their native queue position; direct scheduling is still admitted
     * only for completely bytecode-lowered functions.
     */
    static InstantiatedFunction<CommandSourceStack> compile(
            PlainTextFunction<CommandSourceStack> original
    ) {
        MixedFunctionIR.Program mixed = MixedFunctionIR.lower(original);
        if (mixed.typedRegionCount() == 0
                && mixed.typedCallCount() == 0 && mixed.typedGuardCount() == 0 && mixed.typedStoreCount() == 0
                && mixed.typedContextCallCount() == 0) return original;
        List<UnboundEntryAction<CommandSourceStack>> entries = mixed.executableEntries();
        List<UnboundEntryAction<CommandSourceStack>> directChunks =
                TypedScoreIRDirectScheduler.compilationEnabled()
                        && "bytecode".equals(MODE)
                        ? mixed.directBytecodeChunks() : null;
        if (directChunks != null) TypedScoreIRDirectScheduler.eligibleCompiled();
        return new CompiledFunction(original, entries, directChunks);
    }

    static Instruction lower(UnboundEntryAction<CommandSourceStack> entry) {
        FusedRegionPrototype.FusedCommand parsed = FusedRegionPrototype.fusedCommand(entry);
        if (parsed == null) return null;
        var command = parsed.command().getTopContext().getCommand();
        if (command instanceof ScoreAddCommand mutation) return mutation.toTypedIR(parsed);
        if (command instanceof ScoreOperationCommand binary) return binary.toTypedIR(parsed);
        if (command instanceof ScoreConditionCommand condition) return condition.toTypedIR(parsed);
        return null;
    }

    record EmittedRegion(
            UnboundEntryAction<CommandSourceStack> action,
            boolean bytecode
    ) {
        EmittedRegion { Objects.requireNonNull(action); }
    }

    /**
     * Emit one typed node. A JVM generation failure is an *interpreted typed
     * node*, not an opaque vanilla barrier: direct scheduling must therefore
     * refuse the mixed program, even though the ordinary interpreter remains
     * semantically eligible at the normal Minecraft queue position.
     */
    static EmittedRegion emitRegion(Program program, Identifier functionId) {
        // IR-035: explicit post-lowering optimizer boundary. The optimized plan
        // retains each original Instruction and effect barrier in exact order.
        // Interpreter and ASM consume the SAME immutable opcode/argument plan.
        TypedIROptimizer.Plan optimized = TypedIROptimizer.optimize(program);
        boolean emitBytecode = "bytecode".equals(MODE);
        if (CompilerFixtures.ENABLED && Boolean.parseBoolean(System.getenv("FC_TYPED_IR042_BENCHMARK"))
                && functionId.getNamespace().equals("fc_ir")
                && functionId.getPath().equals("ir017_ir042_interp")) emitBytecode = false;
        UnboundEntryAction<CommandSourceStack> action = new Interpreted(program, optimized);
        boolean bytecode = false;
        if (emitBytecode) {
            try {
                if (CompilerFixtures.ENABLED && Boolean.parseBoolean(System.getenv("FC_TYPED_IR_FORCE_FAILURE"))) {
                    throw new IllegalStateException("IR injected compilation failure");
                }
                action = TypedScoreIRBytecode.emit(optimized);
                bytecode = true;
                if (DIAGNOSTICS) BYTECODE_REGIONS.increment();
            } catch (RuntimeException | LinkageError compileError) {
                FunctionCompilerMod.LOGGER.warn("Typed IR bytecode fallback: {}",
                        compileError.toString());
            }
        }
        if (DIAGNOSTICS) COMPILED_REGIONS.increment();
        return new EmittedRegion(action, bytecode);
    }

    static boolean retainsOriginal(
            InstantiatedFunction<?> compiled,
            InstantiatedFunction<?> original
    ) {
        return compiled instanceof CompiledFunction typed && typed.original() == original;
    }

    /**
     * Only returns immutable generated-bytecode chunks for a fully typed
     * function. A single original command, selector, macro, control-flow
     * barrier, compile failure or uncompiled singleton tail blocks direct
     * scheduling. All other CallFunction contexts stay on vanilla frames.
     */
    static List<UnboundEntryAction<CommandSourceStack>> directFunctionChunks(
            InstantiatedFunction<?> function
    ) {
        return function instanceof CompiledFunction typed ? typed.directChunks() : null;
    }

    /**
     * Traced calls still use vanilla frames. Report the original physical
     * function line count even when the typed compiler collapsed many
     * entries into a handful of generated region actions.
     */
    public static int originalTraceEntryCount(
            InstantiatedFunction<?> function, int observed
    ) {
        return function instanceof CompiledFunction typed
                ? typed.original().entries().size() : observed;
    }

    static void executed() {
        if (DIAGNOSTICS) EXECUTED_REGIONS.increment();
    }

    static void step(Instruction instruction) {
        if (!DIAGNOSTICS) return;
        EXECUTED_STEPS.increment();
        if (instruction instanceof Binary) BINARY_STEPS.increment();
        if (instruction instanceof Conditional || instruction instanceof Compound) CONDITIONAL_STEPS.increment();
        if (instruction instanceof Conditional condition
                && condition.terminal() instanceof Binary) GUARDED_BINARY_STEPS.increment();
        Instruction terminal = instruction instanceof Conditional condition
                ? condition.terminal() : instruction instanceof Compound compound
                        ? compound.terminal() : instruction;
        if (terminal instanceof Binary binary
                && (binary.operation() == BinaryOperator.MINIMUM
                    || binary.operation() == BinaryOperator.MAXIMUM)) MINMAX_STEPS.increment();
    }

    static void skippedConditional() {
        if (DIAGNOSTICS) CONDITIONAL_SKIPS.increment();
    }

    static void fallback() {
        if (DIAGNOSTICS) FALLBACK_STEPS.increment();
    }

    static boolean singletonFeedbackEnabled() {
        return SINGLETON_FEEDBACK && singletonFeedbackRuntime;
    }

    static int toggleSingletonFeedback(CommandSourceStack source, boolean enabled) {
        if (!CompilerFixtures.ENABLED || !SINGLETON_FEEDBACK || !Boolean.parseBoolean(
                System.getenv("FC_TYPED_IR_SINGLETON_FEEDBACK_TOGGLE"))) {
            return 0;
        }
        singletonFeedbackRuntime = enabled;
        source.sendSuccess(() -> net.minecraft.network.chat.Component.literal(
                "IR011 singleton feedback enabled=" + enabled), false);
        return 1;
    }

    static void singletonFeedbackUsed() {
        if (DIAGNOSTICS) SINGLETON_FEEDBACK_STEPS.increment();
    }

    static void trackerFeedbackUsed() {
        if (DIAGNOSTICS) TRACKER_FEEDBACK_STEPS.increment();
    }

    static void reentrantYield() {
        if (DIAGNOSTICS) REENTRANT_YIELDS.increment();
    }

    static void reentrantQueuedStep() {
        if (DIAGNOSTICS) REENTRANT_QUEUED_STEPS.increment();
    }

    static void objectiveLookupReused() {
        if (DIAGNOSTICS) OBJECTIVE_LOOKUPS_REUSED.increment();
    }

    static void comparisonEvaluated() {
        if (DIAGNOSTICS) COMPARISON_EVALUATIONS.increment();
    }

    static void comparisonReadReused() {
        if (DIAGNOSTICS) COMPARISON_READS_REUSED.increment();
    }

    static void compoundStage(boolean reused, boolean pass) {
        if (!DIAGNOSTICS) return;
        COMPOUND_STAGES.increment();
        if (reused) COMPOUND_REUSED.increment();
        if (!pass) COMPOUND_SHORT_CIRCUITS.increment();
    }

    static void compoundFallback() {
        if (DIAGNOSTICS) COMPOUND_FALLBACKS.increment();
    }

    static void compoundEmptyStage() {
        if (DIAGNOSTICS) COMPOUND_EMPTY_STAGES.increment();
    }

    static void dataflowProofUsed() {
        if (DIAGNOSTICS) DATAFLOW_PROOFS.increment();
    }

    static void dataflowReadReused() {
        if (DIAGNOSTICS) DATAFLOW_READS_REUSED.increment();
    }
    static void nativeArithmetic(boolean error) {
        if (DIAGNOSTICS) {
            NATIVE_ARITHMETIC_STEPS.increment();
            if (error) NATIVE_ARITHMETIC_ERRORS.increment();
        }
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
                + " guarded_binary_steps=" + GUARDED_BINARY_STEPS.sum()
                + " conditional_skips=" + CONDITIONAL_SKIPS.sum()




                + " singleton_feedback=" + singletonFeedbackEnabled()
                + " singleton_feedback_steps=" + SINGLETON_FEEDBACK_STEPS.sum()
                + " tracker_feedback_steps=" + TRACKER_FEEDBACK_STEPS.sum()
                + " reentrant_yields=" + REENTRANT_YIELDS.sum()
                + " reentrant_queued_steps=" + REENTRANT_QUEUED_STEPS.sum()
                + " ir037_objective_lookups_reused=" + OBJECTIVE_LOOKUPS_REUSED.sum()
                + " ir038_extended_score=" + EXTENDED_SCORE
                + " ir038_comparisons=" + COMPARISON_EVALUATIONS.sum()
                + " ir038_comparison_reads_reused=" + COMPARISON_READS_REUSED.sum()
                + " ir038_minmax_steps=" + MINMAX_STEPS.sum()
                + " ir039_compound=" + CompoundScoreIR.enabled()
                + " ir039_stages=" + COMPOUND_STAGES.sum()
                + " ir039_reused=" + COMPOUND_REUSED.sum()
                + " ir039_short_circuits=" + COMPOUND_SHORT_CIRCUITS.sum()
                + " ir039_native_fallbacks=" + COMPOUND_FALLBACKS.sum()
                + " ir039_empty_stage_debits=" + COMPOUND_EMPTY_STAGES.sum()
                + " ir040_proofs=" + DATAFLOW_PROOFS.sum()
                + " ir040_operand_reads_reused=" + DATAFLOW_READS_REUSED.sum()
                + " ir040_arithmetic_steps=" + NATIVE_ARITHMETIC_STEPS.sum()
                + " ir040_arithmetic_errors=" + NATIVE_ARITHMETIC_ERRORS.sum()




                + CompilerFixtures.diagnostics()
                + TypedScoreIRDirectScheduler.diagnostics()
                + MixedFunctionIR.diagnostics()
                + TypedFunctionDispatch.diagnostics()
                + TypedContextDispatch.diagnostics()
                + TypedConditionalTerminal.diagnostics()
                + TypedNativeStore.diagnostics()
                + GuardRunReuse.diagnostics()
                + GuardPreflightReuse.diagnostics();
    }

    private record CompiledFunction(
            PlainTextFunction<CommandSourceStack> original,
            List<UnboundEntryAction<CommandSourceStack>> entries,
            List<UnboundEntryAction<CommandSourceStack>> directChunks
    ) implements InstantiatedFunction<CommandSourceStack> {
        @Override
        public Identifier id() { return original.id(); }
    }

    /**
     * Execute exactly one already-validated typed semantic step. Also used
     * by IR-013's exceptional queue continuation: each step is then its own
     * Minecraft EntryAction, allowing queued callback work to run between
     * original source commands. Unlike a previously wrapped Brigadier
     * callback, this does not recurse into ScoreConditionCommand.fallbackChain.
     */
    static int executeTypedStep(
            Instruction instruction, TypedScoreIRRuntime.State state
    ) {
        int decision = state.begin(instruction);
        if (decision != TypedScoreIRRuntime.DIRECT) return decision;
        if (instruction instanceof Compound && !state.completeCompound()) return TypedScoreIRRuntime.SKIP;
        ScoreAccess score = state.access();
        int updated;
        Instruction terminal = instruction instanceof Conditional conditional
                ? conditional.terminal() : instruction instanceof Compound compound
                        ? compound.terminal() : instruction;
        if (terminal instanceof Binary binary) {
            if (binary.operation().nativeArithmetic()) {
                state.applyNativeArithmetic();
                return TypedScoreIRRuntime.DIRECT;
            }
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
                case DIVIDE, MODULO, SWAP -> throw new AssertionError("native arithmetic dispatched separately");
                case MINIMUM, MAXIMUM -> {
                    int value = binary.operation() == BinaryOperator.MINIMUM
                            ? Math.min(score.get(), operand) : Math.max(score.get(), operand);
                    score.set(value);
                    yield value;
                }
            };
        } else {
            Mutation mutation = (Mutation) terminal;
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
        return TypedScoreIRRuntime.DIRECT;
    }

    /**
     * IR-035: execute a compile-time canonicalized ONE-command opcode. The
     * original Instruction still owns quota/tracing, objective guards, native
     * fallback, feedback, and the reentrant queue boundary. Only the opcode
     * dispatch and literal sign are precomputed; scoreboard values are NEVER
     * propagated between instructions.
     */
    static int executeOptimizedStep(
            TypedIROptimizer.Step step,
            TypedIRPreparedSteps.Prepared prepared,
            TypedScoreIRRuntime.State state
    ) {
        int decision = state.begin(prepared);
        if (decision != TypedScoreIRRuntime.DIRECT) return decision;
        if (prepared.compound() != null && !state.completeCompound()) return TypedScoreIRRuntime.SKIP;
        ScoreAccess score = state.access();
        int updated;
        switch (step.opcode()) {
            case ADD_LITERAL -> updated = score.add(step.literal());
            case SET_LITERAL -> {
                score.set(step.literal());
                updated = step.literal();
            }
            case DIVIDE_SCORE, MODULO_SCORE, SWAP_SCORE -> {
                state.applyNativeArithmetic();
                return TypedScoreIRRuntime.DIRECT;
            }
            case ASSIGN_SCORE, ADD_SCORE, SUBTRACT_SCORE, MULTIPLY_SCORE, MIN_SCORE, MAX_SCORE -> {
                int operand = state.sourceAccess().get();
                updated = switch (step.opcode()) {
                    case ASSIGN_SCORE -> {
                        score.set(operand);
                        yield operand;
                    }
                    case ADD_SCORE -> score.add(operand);
                    case SUBTRACT_SCORE -> score.add(-operand);
                    case MULTIPLY_SCORE -> {
                        int product = score.get() * operand;
                        score.set(product);
                        yield product;
                    }
                    case MIN_SCORE, MAX_SCORE -> {
                        int value = step.opcode() == TypedIROptimizer.Op.MIN_SCORE
                                ? Math.min(score.get(), operand) : Math.max(score.get(), operand);
                        score.set(value);
                        yield value;
                    }
                    default -> throw new AssertionError("unreachable canonical opcode");
                };
            }
            default -> throw new AssertionError("unknown canonical opcode");
        }
        state.finish(updated);
        return TypedScoreIRRuntime.DIRECT;
    }

    static final class Interpreted implements UnboundEntryAction<CommandSourceStack> {
        /**
         * IR-034: materialize the already immutable typed region ONCE at
         * compilation. A function may execute thousands of times per tick:
         * never allocate another instruction array for each invocation.
         *
         * State only reads the instruction vector, including when it has to
         * enqueue a fresh continuation on a reentrant callback. No source
         * instruction, per-command effect boundary, or fallback is removed.
         */
        private final Instruction[] steps;
        private final TypedIROptimizer.Step[] opcodes;
        private final TypedIRPreparedSteps.Prepared[] prepared;

        Interpreted(Program program, TypedIROptimizer.Plan optimized) {
            this.steps = program.instructions().toArray(Instruction[]::new);
            this.opcodes = optimized.steps().toArray(TypedIROptimizer.Step[]::new);
            // IR-037: compile-time metadata: no Conditional/Binary/Mutation
            // instanceof dispatch or terminal unwrapping in the execution loop.
            this.prepared = TypedIRPreparedSteps.prepare(optimized);
            if (steps.length != opcodes.length || steps.length != prepared.length) {
                throw new IllegalArgumentException("IR-037 source/plan length mismatch");
            }
        }

        @Override
        public void execute(
                CommandSourceStack source,
                ExecutionContext<CommandSourceStack> context,
                Frame frame
        ) {
            TypedScoreIRRuntime.State state =
                    new TypedScoreIRRuntime.State(source, context, frame, steps);
            executed();
            for (int index = 0; index < opcodes.length; index++) {
                if (executeOptimizedStep(opcodes[index], prepared[index], state)
                        == TypedScoreIRRuntime.STOP) return;
            }
        }
    }

}
