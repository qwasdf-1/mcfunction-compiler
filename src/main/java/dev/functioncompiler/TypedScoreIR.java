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
    private static final String MODE = System.getenv("FC_TYPED_IR_MODE");
    private static final String NAMESPACE = System.getenv("FC_TYPED_IR_NAMESPACE");
    private static final boolean ACTIVE = ("interpreted".equals(MODE) || "bytecode".equals(MODE))
            && NAMESPACE != null && !NAMESPACE.isBlank();
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    // IR-018: dynamic @s scoreboard holder lowering is research-only and
    // independently gated from IR-017 ranged-condition syntax.
    private static final boolean SELF_HOLDER =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SELF_HOLDER"));
    static boolean selfHolderEnabled() { return SELF_HOLDER; }
    static String slotName(ScoreHolder holder, boolean isSelf) {
        return isSelf ? "@s" : holder.getScoreboardName();
    }
    // Requires matching server-scoreboard revision hooks; strict opt-in.
    private static final boolean SCORE_CACHE =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SCORE_CACHE"));
    // Optional research-only same-JVM A/B control. Never available by default.
    private static volatile boolean scoreCacheRuntime = SCORE_CACHE;
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
    private static final LongAdder CACHE_HITS = new LongAdder();
    private static final LongAdder CACHE_MISSES = new LongAdder();
    private static final LongAdder CACHE_INVALIDATIONS = new LongAdder();
    private static final LongAdder SINGLETON_FEEDBACK_STEPS = new LongAdder();
    private static final LongAdder TRACKER_FEEDBACK_STEPS = new LongAdder();
    private static final LongAdder REENTRANT_YIELDS = new LongAdder();
    private static final LongAdder REENTRANT_QUEUED_STEPS = new LongAdder();

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

    /** Only =, +=, -=, *=; no divide-by-zero, swap or multi-write operations. */
    enum BinaryOperator { ASSIGN, ADD, SUBTRACT, MULTIPLY }

    record Binary(
            FusedRegionPrototype.FusedCommand vanilla,
            ScoreHolder holder,
            boolean holderSelf,
            String objective,
            BinaryOperator operation,
            ScoreHolder sourceHolder,
            boolean sourceSelf,
            String sourceObjective
    ) implements Instruction {
        Binary {
            Objects.requireNonNull(vanilla);
            if (!holderSelf) Objects.requireNonNull(holder);
            if (holderSelf && holder != null) throw new IllegalArgumentException("ambiguous target");
            Objects.requireNonNull(objective);
            Objects.requireNonNull(operation);
            if (!sourceSelf) Objects.requireNonNull(sourceHolder);
            if (sourceSelf && sourceHolder != null) throw new IllegalArgumentException("ambiguous source");
            Objects.requireNonNull(sourceObjective);
        }
        @Override
        public Effects effects() {
            Slot target = new Slot(slotName(holder, holderSelf), objective);
            Slot source = new Slot(slotName(sourceHolder, sourceSelf), sourceObjective);
            Set<Slot> reads = new HashSet<>();
            reads.add(source);
            if (operation != BinaryOperator.ASSIGN) reads.add(target);
            return new Effects(reads, Set.of(target), true);
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
            boolean unless
    ) implements Instruction {
        Conditional {
            Objects.requireNonNull(vanilla);
            Objects.requireNonNull(terminal);
            if (!(terminal instanceof Mutation || terminal instanceof Binary)) {
                throw new IllegalArgumentException("conditional terminal must be mutation or binary");
            }
            if (!conditionSelf) Objects.requireNonNull(conditionHolder);
            if (conditionSelf && conditionHolder != null) throw new IllegalArgumentException("ambiguous guard");
            Objects.requireNonNull(conditionObjective);
            Objects.requireNonNull(range);
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
        if (mixed.typedRegionCount() == 0) return original;
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
    ) {}

    /**
     * Emit one typed node. A JVM generation failure is an *interpreted typed
     * node*, not an opaque vanilla barrier: direct scheduling must therefore
     * refuse the mixed program, even though the ordinary interpreter remains
     * semantically eligible at the normal Minecraft queue position.
     */
    static EmittedRegion emitRegion(Program program) {
        UnboundEntryAction<CommandSourceStack> action = new Interpreted(program);
        boolean bytecode = false;
        if ("bytecode".equals(MODE)) {
            try {
                if (Boolean.parseBoolean(System.getenv("FC_TYPED_IR_FORCE_FAILURE"))) {
                    throw new IllegalStateException("IR injected compilation failure");
                }
                action = TypedScoreIRBytecode.emit(program);
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
        if (instruction instanceof Conditional) CONDITIONAL_STEPS.increment();
        if (instruction instanceof Conditional condition
                && condition.terminal() instanceof Binary) GUARDED_BINARY_STEPS.increment();
    }

    static void skippedConditional() {
        if (DIAGNOSTICS) CONDITIONAL_SKIPS.increment();
    }

    static void fallback() {
        if (DIAGNOSTICS) FALLBACK_STEPS.increment();
    }

    static boolean scoreCacheCompiled() { return SCORE_CACHE; }
    static boolean scoreCacheEnabled() { return SCORE_CACHE && scoreCacheRuntime; }

    static int toggleCache(CommandSourceStack source, boolean enabled) {
        if (!SCORE_CACHE || !Boolean.parseBoolean(
                System.getenv("FC_TYPED_IR_SCORE_CACHE_TOGGLE"))) {
            return 0;
        }
        scoreCacheRuntime = enabled;
        source.sendSuccess(() -> net.minecraft.network.chat.Component.literal(
                "IR010 cache enabled=" + enabled), false);
        return 1;
    }
    static boolean singletonFeedbackEnabled() {
        return SINGLETON_FEEDBACK && singletonFeedbackRuntime;
    }

    static int toggleSingletonFeedback(CommandSourceStack source, boolean enabled) {
        if (!SINGLETON_FEEDBACK || !Boolean.parseBoolean(
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

    static void cacheHit() { if (DIAGNOSTICS) CACHE_HITS.increment(); }
    static void cacheMiss() { if (DIAGNOSTICS) CACHE_MISSES.increment(); }
    static void cacheInvalidated() {
        if (DIAGNOSTICS) CACHE_INVALIDATIONS.increment();
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
                + " score_cache=" + scoreCacheEnabled()
                + " cache_hits=" + CACHE_HITS.sum()
                + " cache_misses=" + CACHE_MISSES.sum()
                + " cache_invalidations=" + CACHE_INVALIDATIONS.sum()
                + " singleton_feedback=" + singletonFeedbackEnabled()
                + " singleton_feedback_steps=" + SINGLETON_FEEDBACK_STEPS.sum()
                + " tracker_feedback_steps=" + TRACKER_FEEDBACK_STEPS.sum()
                + " reentrant_yields=" + REENTRANT_YIELDS.sum()
                + " reentrant_queued_steps=" + REENTRANT_QUEUED_STEPS.sum()
                + ReentrantQueueProbe.diagnostics()
                + TypedScoreIRDirectScheduler.diagnostics()
                + MixedFunctionIR.diagnostics();
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
        ScoreAccess score = state.access();
        int updated;
        Instruction terminal = instruction instanceof Conditional conditional
                ? conditional.terminal() : instruction;
        if (terminal instanceof Binary binary) {
            int operand = SCORE_CACHE
                    ? state.sourceOperand() : state.sourceAccess().get();
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
                    new TypedScoreIRRuntime.State(
                            source, context, frame,
                            program.instructions().toArray(TypedScoreIR.Instruction[]::new));
            executed();
            for (Instruction instruction : program.instructions()) {
                if (executeTypedStep(instruction, state) == TypedScoreIRRuntime.STOP) return;
            }
        }
    }

}
