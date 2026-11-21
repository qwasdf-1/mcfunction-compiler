package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import net.minecraft.resources.Identifier;
import net.minecraft.network.chat.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

/**
 * COMPILER-IR-016: immutable, source-positioned mixed function IR.
 *
 * The semantic unit is an original Minecraft function entry, not a scoreboard
 * write. A typed region may replace 2..64 consecutive validated entries; an
 * opaque barrier retains the EXACT original UnboundEntryAction at that source
 * position. No optimizer can legally move across an opaque barrier, including
 * /function, /return, forked execute, macro or modded commands.
 *
 * The initial backend materializes these nodes to native queue entries: it
 * deliberately does NOT schedule opaque actions from a custom direct cursor.
 * The only direct-scheduler admission remains an all-bytecode program.
 */
final class MixedFunctionIR {
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static final int MAX_LEDGER_FUNCTIONS = 2048;
    private static final int MAX_LAYOUT_NODES = 24;
    private static final ConcurrentHashMap<String, String> LEDGER =
            new ConcurrentHashMap<>();
    private static final LongAdder VISITED = new LongAdder();
    private static final LongAdder MIXED = new LongAdder();
    private static final LongAdder TYPED_NODES = new LongAdder();
    private static final LongAdder TYPED_LINES = new LongAdder();
    private static final LongAdder OPAQUE_NODES = new LongAdder();
    private static final LongAdder SINGLETON_NODES = new LongAdder();
    private static final LongAdder DISPATCH_BARRIERS = new LongAdder();
    // IR-018 audit classification only. Conditional function calls retain
    // their original EntryAction; no child-frame semantics are synthesized.
    private static final java.util.regex.Pattern DISPATCH_SOURCE =
            java.util.regex.Pattern.compile(
                    "^execute (?:if|unless) score .+ run function .+$");

    private MixedFunctionIR() {}

    sealed interface Node permits TypedRegion, OpaqueBarrier, NativeForkPlanBarrier {
        int firstSourceIndex();
        int sourceCount();
        UnboundEntryAction<CommandSourceStack> action();
    }

    record TypedRegion(
            int firstSourceIndex,
            TypedScoreIR.Program typed,
            UnboundEntryAction<CommandSourceStack> action,
            boolean bytecode
    ) implements Node {
        TypedRegion {
            if (firstSourceIndex < 0) throw new IllegalArgumentException("negative source index");
            java.util.Objects.requireNonNull(typed);
            java.util.Objects.requireNonNull(action);
        }

        @Override
        public int sourceCount() { return typed.instructions().size(); }
    }

    enum BarrierKind { UNSUPPORTED_OR_CONTROL, FUNCTION_DISPATCH, TYPED_SINGLETON }

    record OpaqueBarrier(
            int firstSourceIndex,
            UnboundEntryAction<CommandSourceStack> action,
            BarrierKind kind
    ) implements Node {
        OpaqueBarrier {
            if (firstSourceIndex < 0) throw new IllegalArgumentException("negative source index");
            java.util.Objects.requireNonNull(action);
            java.util.Objects.requireNonNull(kind);
        }

        @Override
        public int sourceCount() { return 1; }
    }

    /**
     * IR-024 recognized post-Brigadier fork, but NEVER a selector replacement.
     * An original native queue action remains in the exact same source slot.
     * The existing typed bytecode direct scheduler declines this node.
     */
    record NativeForkPlanBarrier(
            int firstSourceIndex,
            CompilerForkPlan024.Plan plan,
            UnboundEntryAction<CommandSourceStack> action
    ) implements Node {
        NativeForkPlanBarrier {
            if (firstSourceIndex < 0) throw new IllegalArgumentException("negative source index");
            java.util.Objects.requireNonNull(plan);
            java.util.Objects.requireNonNull(action);
        }
        @Override public int sourceCount() { return 1; }
    }

    record Program(Identifier id, int sourceCount, List<Node> nodes) {
        Program {
            java.util.Objects.requireNonNull(id);
            nodes = List.copyOf(nodes);
            if (sourceCount < 0 || sourceCount < nodes.size()) {
                throw new IllegalArgumentException("invalid original function size");
            }
            // This is a code-generation correctness assertion: every source
            // entry occurs once and in original order, with no holes or overlap.
            int expected = 0;
            for (Node node : nodes) {
                if (node.firstSourceIndex() != expected || node.sourceCount() <= 0) {
                    throw new IllegalArgumentException(
                            "IR016 source span gap or overlap at " + expected);
                }
                if (node instanceof TypedRegion region) {
                    if (region.sourceCount() < 2
                            || region.sourceCount() > TypedScoreIR.MAX_REGION_LENGTH) {
                        throw new IllegalArgumentException("invalid typed region length");
                    }
                    for (TypedScoreIR.Instruction instruction
                            : region.typed().instructions()) {
                        if (!instruction.effects().observableBoundary()) {
                            throw new IllegalArgumentException(
                                    "typed instruction has no effect boundary");
                        }
                    }
                }
                expected += node.sourceCount();
            }
            if (expected != sourceCount) {
                throw new IllegalArgumentException(
                        "IR016 original function entries were dropped or duplicated");
            }
        }

        int typedRegionCount() {
            return (int) nodes.stream().filter(TypedRegion.class::isInstance).count();
        }

        int typedSourceCount() {
            return nodes.stream().filter(TypedRegion.class::isInstance)
                    .mapToInt(Node::sourceCount).sum();
        }

        int opaqueCount() {
            return (int) nodes.stream().filter(OpaqueBarrier.class::isInstance).count();
        }

        int singletonCount() {
            return (int) nodes.stream().filter(n -> n instanceof OpaqueBarrier b
                    && b.kind() == BarrierKind.TYPED_SINGLETON).count();
        }

        int dispatchBarrierCount() {
            return (int) nodes.stream().filter(n -> n instanceof OpaqueBarrier b
                    && b.kind() == BarrierKind.FUNCTION_DISPATCH).count();
        }

        int nativeForkPlanCount() {
            return (int) nodes.stream().filter(NativeForkPlanBarrier.class::isInstance).count();
        }

        List<UnboundEntryAction<CommandSourceStack>> executableEntries() {
            return List.copyOf(nodes.stream().map(Node::action).toList());
        }

        /**
         * This returns null unless EVERY node is generated JVM code.
         * Crucially, a call, return, macro, singleton or backend failure
         * cannot be sneaked into IR-012's no-child-frame direct cursor.
         */
        List<UnboundEntryAction<CommandSourceStack>> directBytecodeChunks() {
            if (sourceCount < 2 || sourceCount > 4096
                    || typedRegionCount() == 0 || typedSourceCount() != sourceCount
                    || nodes.stream().anyMatch(n -> !(n instanceof TypedRegion t)
                            || !t.bytecode())) {
                return null;
            }
            return executableEntries();
        }

        String summary() {
            StringBuilder layout = new StringBuilder();
            int count = 0;
            for (Node node : nodes) {
                if (count++ >= MAX_LAYOUT_NODES) {
                    layout.append(",...");
                    break;
                }
                if (!layout.isEmpty()) layout.append(',');
                layout.append(node instanceof TypedRegion t
                        ? (t.bytecode() ? "J" : "I")
                        : node instanceof NativeForkPlanBarrier ? "N"
                        : node instanceof OpaqueBarrier b
                            && b.kind() == BarrierKind.TYPED_SINGLETON ? "S"
                        : node instanceof OpaqueBarrier b
                            && b.kind() == BarrierKind.FUNCTION_DISPATCH ? "F" : "V");
                layout.append(node.firstSourceIndex() + 1).append(':')
                        .append(node.sourceCount());
            }
            return "IR016 function=" + id + " source_lines=" + sourceCount
                    + " typed_lines=" + typedSourceCount()
                    + " typed_regions=" + typedRegionCount()
                    + " opaque_barriers=" + opaqueCount()
                    + " singleton_barriers=" + singletonCount()
                    + " dispatch_barriers=" + dispatchBarrierCount()
                    + " native_fork_plans=" + nativeForkPlanCount()
                    + " direct_candidate=" + (directBytecodeChunks() != null)
                    + " layout=" + layout;
        }
    }

    static Program lower(PlainTextFunction<CommandSourceStack> original) {
        List<Node> nodes = new ArrayList<>();
        List<TypedScoreIR.Instruction> pending = new ArrayList<>();
        List<UnboundEntryAction<CommandSourceStack>> entries = original.entries();
        int first = 0;
        for (int index = 0; index < entries.size(); index++) {
            UnboundEntryAction<CommandSourceStack> entry = entries.get(index);
            TypedScoreIR.Instruction instruction = TypedScoreIR.lower(entry);
            if (instruction == null) {
                flush(nodes, pending, first);
                CompilerForkPlan024.Plan plan = CompilerForkPlan024.classify(entry);
                if (plan != null) {
                    // Compiler admission, NOT code generation: original
                    // BuildContexts.Unbound still executes all native stages.
                    nodes.add(new NativeForkPlanBarrier(index, plan, entry));
                } else {
                    nodes.add(new OpaqueBarrier(index, entry,
                            isFunctionDispatch(entry) ? BarrierKind.FUNCTION_DISPATCH
                                    : BarrierKind.UNSUPPORTED_OR_CONTROL));
                }
            } else {
                if (pending.isEmpty()) first = index;
                if (pending.size() == TypedScoreIR.MAX_REGION_LENGTH) {
                    flush(nodes, pending, first);
                    first = index;
                }
                pending.add(instruction);
            }
        }
        flush(nodes, pending, first);
        Program program = new Program(original.id(), entries.size(), nodes);
        if (DIAGNOSTICS) {
            VISITED.increment();
            if (program.typedRegionCount() > 0 && program.opaqueCount() > 0) MIXED.increment();
            TYPED_NODES.add(program.typedRegionCount());
            TYPED_LINES.add(program.typedSourceCount());
            OPAQUE_NODES.add(program.opaqueCount());
            SINGLETON_NODES.add(program.singletonCount());
            DISPATCH_BARRIERS.add(program.dispatchBarrierCount());
            if (LEDGER.size() < MAX_LEDGER_FUNCTIONS) {
                LEDGER.put(program.id().toString(), program.summary());
            }
        }
        return program;
    }

    /**
     * Source-shape reporting ONLY: function calls are not typed instructions.
     * The exact original Minecraft BuildContexts action is preserved, even if
     * this deliberately broad classification matches more than one stage.
     */
    private static boolean isFunctionDispatch(
            UnboundEntryAction<CommandSourceStack> entry
    ) {
        if (!(entry instanceof BuildContexts.Unbound<?>)) return false;
        String source = ((BuildContextsAccessor<CommandSourceStack>) (Object) entry)
                .functionCompiler$getCommandInput();
        return source != null && DISPATCH_SOURCE.matcher(source).matches();
    }

    private static void flush(
            List<Node> nodes,
            List<TypedScoreIR.Instruction> pending,
            int first
    ) {
        if (pending.isEmpty()) return;
        if (pending.size() == 1) {
            // Even a successfully validated isolated typed command remains
            // its exact original queue action. The singleton is not a region.
            nodes.add(new OpaqueBarrier(first,
                    pending.getFirst().vanilla().original(), BarrierKind.TYPED_SINGLETON));
        } else {
            TypedScoreIR.Program typed = new TypedScoreIR.Program(pending);
            TypedScoreIR.EmittedRegion emitted = TypedScoreIR.emitRegion(typed);
            nodes.add(new TypedRegion(first, typed, emitted.action(), emitted.bytecode()));
        }
        pending.clear();
    }

    static String diagnostics() {
        return " ir016_visited=" + VISITED.sum()
                + " ir016_mixed_functions=" + MIXED.sum()
                + " ir016_typed_regions=" + TYPED_NODES.sum()
                + " ir016_typed_lines=" + TYPED_LINES.sum()
                + " ir016_opaque_barriers=" + OPAQUE_NODES.sum()
                + " ir016_singletons=" + SINGLETON_NODES.sum()
                + " ir018_dispatch_barriers=" + DISPATCH_BARRIERS.sum();
    }

    static int report(CommandSourceStack source, String id) {
        String result = DIAGNOSTICS ? LEDGER.get(id) : null;
        String message = result == null ? "IR016 no ledger entry for " + id : result;
        source.sendSuccess(() -> Component.literal(message), false);
        return 1;
    }
}
