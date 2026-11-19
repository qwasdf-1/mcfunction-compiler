package dev.functioncompiler;

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
import java.util.List;
import java.util.Objects;
import java.util.concurrent.atomic.LongAdder;

/**
 * COMPILER-IR-008. A genuine typed, reload-scoped IR for a deliberately small
 * subset of vanilla-parsed scoreboard instructions. This prototype does NOT
 * accept dynamic selectors, execute modifiers, macro bodies or unparsed input.
 *
 * The interpreter and JVM bytecode share one immutable IR and one exact
 * quota/tracing/response runtime. Unlike BytecodeRegionEmitter, the new ASM
 * backend calls ScoreAccess.add/set directly, never executeStep or Brigadier
 * ContextChain.runExecutable on its accepted path.
 *
 * This is an env-only research mode, restricted to a named namespace. It is
 * not a new production default or a general-purpose Minecraft compiler.
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

    private TypedScoreIR() {}

    static boolean enabledFor(Identifier id) {
        return ACTIVE && id != null && NAMESPACE.equals(id.getNamespace())
                && !ProbeConfiguration.isNamespaceExcluded(id.getNamespace());
    }

    /** Validated typed instruction, with the original parsed command retained. */
    record Instruction(
            FusedRegionPrototype.FusedCommand vanilla,
            ScoreHolder holder,
            String objective,
            ScoreAddCommand.Operation operation,
            int amount
    ) {
        Instruction {
            Objects.requireNonNull(vanilla);
            Objects.requireNonNull(holder);
            Objects.requireNonNull(objective);
            Objects.requireNonNull(operation);
        }
    }

    /** One immutable sequence, not a collection of arbitrary callback objects. */
    record Program(List<Instruction> instructions) {
        Program {
            instructions = List.copyOf(instructions);
            if (instructions.size() < 2 || instructions.size() > MAX_REGION_LENGTH) {
                throw new IllegalArgumentException("IR-008 region length outside [2,64]");
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
                result.add(entry); // Unrecognized input is EXACTLY the vanilla entry.
                continue;
            }
            if (pending.size() == MAX_REGION_LENGTH) {
                changed |= flush(result, pending);
            }
            pending.add(instruction);
        }
        changed |= flush(result, pending);
        return changed ? new CompiledFunction(original, List.copyOf(result)) : original;
    }

    private static Instruction lower(UnboundEntryAction<CommandSourceStack> entry) {
        // This stage is already validated by vanilla Brigadier and recognized
        // by ScoreAddPrototype; no textual reparse or new command registration.
        FusedRegionPrototype.FusedCommand parsed = FusedRegionPrototype.fusedCommand(entry);
        if (parsed == null || !(parsed.command().getTopContext().getCommand()
                instanceof ScoreAddCommand score)) {
            return null;
        }
        return score.toTypedIR(parsed);
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
                    throw new IllegalStateException("IR-008 injected compile failure");
                }
                action = TypedScoreIRBytecode.emit(program);
                if (DIAGNOSTICS) BYTECODE_REGIONS.increment();
            } catch (RuntimeException | LinkageError compileError) {
                // An inaccessible/verifier-incompatible generated class never
                // causes partial world effects. The IR interpreter is the
                // deliberate backup; per-command original entries are retained
                // within each instruction for runtime validation fallbacks.
                FunctionCompilerMod.LOGGER.warn("IR-008 bytecode compilation fell back: {}",
                        compileError.toString());
            }
        }
        result.add(action);
        if (DIAGNOSTICS) COMPILED_REGIONS.increment();
        pending.clear();
        return true;
    }

    static void executed() {
        if (DIAGNOSTICS) EXECUTED_REGIONS.increment();
    }

    static void step() {
        if (DIAGNOSTICS) EXECUTED_STEPS.increment();
    }

    static void fallback() {
        if (DIAGNOSTICS) FALLBACK_STEPS.increment();
    }

    static String diagnosticStatus() {
        if (!ACTIVE) return "IR008 disabled";
        return "IR008 mode=" + MODE + " namespace=" + NAMESPACE
                + " compiled_regions=" + COMPILED_REGIONS.sum()
                + " bytecode_regions=" + BYTECODE_REGIONS.sum()
                + " executed_regions=" + EXECUTED_REGIONS.sum()
                + " executed_steps=" + EXECUTED_STEPS.sum()
                + " fallback_steps=" + FALLBACK_STEPS.sum();
    }

    private record CompiledFunction(
            PlainTextFunction<CommandSourceStack> original,
            List<UnboundEntryAction<CommandSourceStack>> entries
    ) implements InstantiatedFunction<CommandSourceStack> {
        @Override
        public Identifier id() {
            return original.id();
        }
    }

    static final class Interpreted implements UnboundEntryAction<CommandSourceStack> {
        private final Program program;

        Interpreted(Program program) {
            this.program = program;
        }

        @Override
        public void execute(
                CommandSourceStack source,
                ExecutionContext<CommandSourceStack> context,
                Frame frame
        ) {
            TypedScoreIRRuntime.State state = new TypedScoreIRRuntime.State(source, context, frame);
            executed();
            for (Instruction instruction : program.instructions()) {
                int decision = state.begin(instruction);
                if (decision == TypedScoreIRRuntime.STOP) return;
                if (decision == TypedScoreIRRuntime.FALLBACK) continue;
                ScoreAccess score = state.access();
                int updated = switch (instruction.operation()) {
                    case ADD -> score.add(instruction.amount());
                    case REMOVE -> score.add(-instruction.amount());
                    case SET -> {
                        score.set(instruction.amount());
                        yield instruction.amount();
                    }
                };
                state.finish(updated);
            }
        }
    }
}
