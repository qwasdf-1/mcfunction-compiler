package dev.functioncompiler;

import com.mojang.brigadier.context.ContextChain;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ChainModifiers;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.ExecutionControl;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.resources.Identifier;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;

import java.util.List;
import java.util.concurrent.atomic.LongAdder;
import java.util.regex.Pattern;

/**
 * IR043: typed static-call control-flow boundary. Compile only pure score
 * modifiers; delegate the parsed terminal CustomCommandExecutor with its
 * original execution chain, native frame and live function resolution.
 */
final class TypedFunctionDispatch {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DISPATCH"));
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static final Pattern TARGET = Pattern.compile("^function ([a-z0-9_.-]+:[a-z0-9_./-]+)$");
    private static final LongAdder LOWERED = new LongAdder(), ENTERED = new LongAdder(),
            CALLS = new LongAdder(), SKIPPED = new LongAdder(), FALLBACK = new LongAdder(),
            REUSED = new LongAdder(), EMPTY_DEBITS = new LongAdder(), PROOFS = new LongAdder();
    private TypedFunctionDispatch() {}

    record Plan(UnboundEntryAction<CommandSourceStack> original, String input, Identifier target,
                ContextChain<CommandSourceStack> terminal,
                CustomCommandExecutor<CommandSourceStack> executor,
                CompoundScoreIR.Plan predicates) implements UnboundEntryAction<CommandSourceStack> {
        @Override public void execute(CommandSourceStack source, ExecutionContext<CommandSourceStack> context,
                                      Frame frame) {
            if (DIAGNOSTICS) ENTERED.increment();
            // Delegate before any debit or effect. Trace and arbitrary result
            // callbacks retain the exact full native BuildContexts action.
            if (context.tracer() != null || source.callback() != CommandResultCallback.EMPTY
                    || (!predicates.stages().isEmpty() && context.forkLimit() <= 1)) {
                fallback(source, context, frame);
                return;
            }
            if (predicates.stages().isEmpty()) {
                invoke(source, context, frame, ChainModifiers.DEFAULT);
                return;
            }
            Scoreboard board = source.getServer().getScoreboard();
            // Single-stage common case: avoid allocation of guard scratch.
            if (predicates.stages().size() == 1) {
                var stage = predicates.stages().getFirst();
                var left = stage.predicate().left();
                var right = stage.predicate().right();
                Objective lo = board.getObjective(left.objective());
                Objective ro = right == null ? null : left.objective().equals(right.objective())
                        ? lo : board.getObjective(right.objective());
                ScoreHolder lh = left.self() ? source.getEntity() : left.holder();
                ScoreHolder rh = right == null ? null : right.self() ? source.getEntity() : right.holder();
                if (lo == null || lh == null || (right != null && (ro == null || rh == null))) {
                    fallback(source, context, frame);
                    return;
                }
                boolean pass;
                context.profiler().push(() -> input);
                try {
                    context.incrementCost();
                    var l = board.getPlayerScoreInfo(lh, lo);
                    boolean matched = false;
                    if (l != null) {
                        if (right == null) matched = stage.predicate().range().matches(l.value());
                        else {
                            var r = stage.leftIndex() == stage.rightIndex() ? l : board.getPlayerScoreInfo(rh, ro);
                            matched = r != null && ScoreConditionCommand.compareScores(
                                    l.value(), r.value(), stage.predicate().comparison());
                        }
                    }
                    pass = matched != stage.predicate().unless();
                } finally { context.profiler().pop(); }
                if (pass) invoke(source, context, frame, ChainModifiers.DEFAULT.setForked());
                else if (DIAGNOSTICS) SKIPPED.increment();
                return;
            }
            int n = predicates.slots().size();
            Objective[] objectives = new Objective[predicates.objectives().size()];
            ScoreHolder[] holders = new ScoreHolder[n];
            for (int i = 0; i < objectives.length; i++) {
                objectives[i] = board.getObjective(predicates.objectives().get(i));
                if (objectives[i] == null) { fallback(source, context, frame); return; }
            }
            for (int i = 0; i < n; i++) {
                var operand = predicates.slots().get(i).operand();
                holders[i] = operand.self() ? source.getEntity() : operand.holder();
                if (holders[i] == null) { fallback(source, context, frame); return; }
            }
            boolean pass = true;
            int[] values = new int[n];
            int visited = 0, present = 0;
            context.profiler().push(() -> input);
            try {
                for (var stage : predicates.stages()) {
                    // Native BuildContexts charges remaining modifiers even
                    // on the empty-source path and does not gate mid-chain.
                    context.incrementCost();
                    if (!pass) { if (DIAGNOSTICS) EMPTY_DEBITS.increment(); continue; }
                    if (stage.evaluation() != CompoundScoreIR.Evaluation.READ) {
                        if (DIAGNOSTICS) {
                            REUSED.increment();
                            if (stage.dataflowProven()) PROOFS.increment();
                        }
                        pass = stage.evaluation() == CompoundScoreIR.Evaluation.KNOWN_PASS;
                        continue;
                    }
                    int left = stage.leftIndex(), right = stage.rightIndex();
                    int bit = 1 << left;
                    if (!predicates.dataflow() || (visited & bit) == 0) {
                        var info = board.getPlayerScoreInfo(holders[left],
                                objectives[predicates.slots().get(left).objectiveIndex()]);
                        visited |= bit;
                        if (info != null) { present |= bit; values[left] = info.value(); }
                    } else if (DIAGNOSTICS) REUSED.increment();
                    boolean matched = false;
                    if ((present & bit) != 0) {
                        if (right == -1) matched = stage.predicate().range().matches(values[left]);
                        else {
                            int rb = 1 << right;
                            if (right != left && (!predicates.dataflow() || (visited & rb) == 0)) {
                                var info = board.getPlayerScoreInfo(holders[right],
                                        objectives[predicates.slots().get(right).objectiveIndex()]);
                                visited |= rb;
                                if (info != null) { present |= rb; values[right] = info.value(); }
                            } else if (DIAGNOSTICS) REUSED.increment();
                            matched = (present & rb) != 0 && ScoreConditionCommand.compareScores(
                                    values[left], values[right], stage.predicate().comparison());
                        }
                    }
                    pass = matched != stage.predicate().unless();
                }
            } finally { context.profiler().pop(); }
            if (pass) invoke(source, context, frame, ChainModifiers.DEFAULT.setForked());
            else if (DIAGNOSTICS) SKIPPED.increment();
        }
        private void invoke(CommandSourceStack source, ExecutionContext<CommandSourceStack> context,
                            Frame frame, ChainModifiers modifiers) {
            if (DIAGNOSTICS) CALLS.increment();
            // Native BuildContexts invokes custom terminals immediately even
            // after the modifier budget reaches zero. Do not charge an
            // ExecuteCommand debit or synthesize a child CallFunction task.
            executor.run(source, terminal, modifiers, ExecutionControl.create(context, frame));
        }
        private void fallback(CommandSourceStack source, ExecutionContext<CommandSourceStack> context, Frame frame) {
            if (DIAGNOSTICS) FALLBACK.increment();
            original.execute(source, context, frame);
        }
    }

    @SuppressWarnings("unchecked")
    static Plan lower(UnboundEntryAction<CommandSourceStack> original, Identifier functionId) {
        if (!ENABLED || !TypedScoreIR.enabledFor(functionId)
                || ProbeConfiguration.scoreAddPrototypeEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()
                || ProbeConfiguration.fusedRegionPrototypeEnabled()
                || ProbeConfiguration.bytecodeRegionPrototypeEnabled()
                || !(original instanceof BuildContexts.Unbound<?> unbound)) return null;
        var access = (BuildContextsAccessor<CommandSourceStack>) (Object) unbound;
        String input = access.functionCompiler$getCommandInput();
        if (input == null) return null;
        String terminalText = input;
        String[] parts = new String[0];
        if (input.startsWith("execute ")) {
            String[] halves = input.substring(8).split(" run ", -1);
            if (halves.length != 2) return null;
            terminalText = halves[1];
            parts = halves[0].split(" (?=(?:if|unless) score )", -1);
            if (parts.length > CompoundScoreIR.MAX_PREDICATES) return null;
            if (parts.length > 1 && !CompoundScoreIR.enabled()) return null;
        }
        var matcher = TARGET.matcher(terminalText);
        if (!matcher.matches()) return null;
        Identifier target = Identifier.tryParse(matcher.group(1));
        if (target == null) return null;
        var chain = access.functionCompiler$getCommand();
        if ((chain.getStage() == ContextChain.Stage.EXECUTE) != (parts.length == 0)) return null;
        List<CompoundScoreIR.Predicate> predicates = parts.length == 0 ? List.of()
                : ScoreAddPrototype.parseDispatchPredicates(chain, parts);
        if (predicates == null) return null;
        while (chain.getStage() != ContextChain.Stage.EXECUTE) chain = chain.nextStage();
        var terminal = chain.getTopContext();
        if (!ScoreAddPrototype.nodeNames(terminal).equals(List.of("function", "name"))
                || !matcher.group(1).equals(ScoreAddPrototype.extractNodeText(terminal, "name"))
                || terminal.isForked()
                || !(terminal.getCommand() instanceof CustomCommandExecutor<?> custom)) return null;
        var plan = CompoundScoreIR.preparePredicates(predicates,
                CompoundScoreIR.dataflowEnabledFor(functionId), null, null);
        if (DIAGNOSTICS) LOWERED.increment();
        return new Plan(original, input, target, chain,
                (CustomCommandExecutor<CommandSourceStack>) custom, plan);
    }

    static String diagnostics() {
        return " ir043_lowered=" + LOWERED.sum() + " ir043_entered=" + ENTERED.sum()
                + " ir043_calls=" + CALLS.sum() + " ir043_skipped=" + SKIPPED.sum()
                + " ir043_fallbacks=" + FALLBACK.sum() + " ir043_reused=" + REUSED.sum()
                + " ir043_empty_debits=" + EMPTY_DEBITS.sum() + " ir043_proofs=" + PROOFS.sum();
    }
}
