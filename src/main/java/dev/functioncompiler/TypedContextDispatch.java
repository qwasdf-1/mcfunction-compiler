package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.ContextChainAccessor;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ChainModifiers;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.CustomModifierExecutor;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.ExecutionControl;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.resources.Identifier;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.concurrent.atomic.LongAdder;
import java.util.regex.Pattern;

/** IR048: bounded native context dispatch. Empty/singleton stages avoid
 * accumulator lists; multi-source stages retain ordered native redirects.
 * No selector, score predicate, source transformation or child scheduler
 * is reimplemented. Plans retain only parsed immutable command structure. */
final class TypedContextDispatch {
    private static final boolean ENABLED =
            TypedCompilerConfiguration.flag("FC_TYPED_IR_CONTEXT_DISPATCH");
    private static final boolean DIAGNOSTICS =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static final Pattern TARGET =
            Pattern.compile("function [a-z0-9_.-]+:[a-z0-9_./-]+");
    private static final ChainModifiers FORKED = ChainModifiers.DEFAULT.setForked();
    private static final LongAdder LOWERED = new LongAdder(), ENTERED = new LongAdder(),
            EMPTY = new LongAdder(), SINGLE = new LongAdder(), MULTI = new LongAdder(),
            FALLBACK = new LongAdder(), DEBITS = new LongAdder(),
            EMPTY_DEBITS = new LongAdder(), MODIFIERS = new LongAdder(),
            MULTI_STAGES = new LongAdder(), TERMINALS = new LongAdder(),
            ERRORS = new LongAdder(), LIMIT_ERRORS = new LongAdder();

    private TypedContextDispatch() {}

    record Plan(UnboundEntryAction<CommandSourceStack> original, String input,
                List<CommandContext<CommandSourceStack>> stages,
                ContextChain<CommandSourceStack> terminal,
                CustomCommandExecutor<CommandSourceStack> executor)
            implements UnboundEntryAction<CommandSourceStack> {
        Plan {
            stages = List.copyOf(stages);
        }

        @Override public void execute(CommandSourceStack source,
                ExecutionContext<CommandSourceStack> context, Frame frame) {
            if (DIAGNOSTICS) ENTERED.increment();
            // Fallback only before any native modifier, debit or effect.
            if (context.tracer() != null || source.callback() != CommandResultCallback.EMPTY
                    || context.forkLimit() <= 1) {
                if (DIAGNOSTICS) FALLBACK.increment();
                original.execute(source, context, frame);
                return;
            }
            CommandSourceStack single = source;
            List<CommandSourceStack> many = null;
            int limit = context.forkLimit();
            context.profiler().push(() -> input);
            try {
                for (var stage : stages) {
                    // Native BuildContexts charges each non-null redirect even
                    // on an empty source list. The trailing run is a no-op.
                    context.incrementCost();
                    if (DIAGNOSTICS) DEBITS.increment();
                    if (single == null && many == null) {
                        if (DIAGNOSTICS) EMPTY_DEBITS.increment();
                        continue;
                    }
                    if (many == null) {
                        Collection<CommandSourceStack> out = run(stage, single, context);
                        if (out.size() >= limit) {
                            limitError(source, context, limit);
                            return;
                        }
                        if (out.isEmpty()) {
                            single = null;
                        } else if (out.size() == 1) {
                            single = out.iterator().next();
                        } else {
                            many = new ArrayList<>(out);
                            single = null;
                        }
                    } else {
                        // Once a stage fans out, preserve its ordered input
                        // iteration and cumulative limit. Never replay a
                        // modifier or fall back after executing any stage.
                        if (DIAGNOSTICS) MULTI_STAGES.increment();
                        List<CommandSourceStack> next = new ArrayList<>();
                        for (CommandSourceStack transformed : many) {
                            Collection<CommandSourceStack> out = run(stage, transformed, context);
                            if (next.size() + out.size() >= limit) {
                                limitError(source, context, limit);
                                return;
                            }
                            next.addAll(out);
                        }
                        single = next.size() == 1 ? next.getFirst() : null;
                        many = next.size() > 1 ? next : null;
                    }
                }
            } finally {
                context.profiler().pop();
            }
            // Native custom-terminal calls are immediate in BuildContexts,
            // even after the modifier debit reaches zero. Reuse one control
            // for the ordered returned sources; no ExecuteCommand debit.
            if (single == null && many == null) {
                if (DIAGNOSTICS) EMPTY.increment();
                return;
            }
            var control = ExecutionControl.create(context, frame);
            if (many == null) {
                if (DIAGNOSTICS) { SINGLE.increment(); TERMINALS.increment(); }
                executor.run(single, terminal, FORKED, control);
            } else {
                if (DIAGNOSTICS) MULTI.increment();
                for (CommandSourceStack transformed : many) {
                    if (DIAGNOSTICS) TERMINALS.increment();
                    executor.run(transformed, terminal, FORKED, control);
                }
            }
        }
    }

    private static Collection<CommandSourceStack> run(
            CommandContext<CommandSourceStack> stage, CommandSourceStack source,
            ExecutionContext<CommandSourceStack> context) {
        if (DIAGNOSTICS) MODIFIERS.increment();
        try {
            return ContextChain.runModifier(stage, source, (c, success, result) -> {}, true);
        } catch (CommandSyntaxException error) {
            // All admitted redirects are forked. Native handles a failing
            // source independently and continues the remaining source list.
            if (DIAGNOSTICS) ERRORS.increment();
            source.handleError(error, true, context.tracer());
            return List.of();
        }
    }

    private static void limitError(CommandSourceStack original,
                                   ExecutionContext<CommandSourceStack> context, int limit) {
        if (DIAGNOSTICS) LIMIT_ERRORS.increment();
        original.handleError(BuildContexts.ERROR_FORK_LIMIT_REACHED.create(limit),
                true, context.tracer());
    }

    private enum Kind { AS, AT_SELF, SCORE }

    private static String text(CommandContext<CommandSourceStack> c) {
        var nodes = c.getNodes();
        if (nodes.isEmpty()) return "";
        return c.getInput().substring(nodes.getFirst().getRange().getStart(),
                nodes.getLast().getRange().getEnd());
    }

    private static Kind classify(CommandContext<CommandSourceStack> c, boolean first) {
        if (!c.isForked() || c.getRedirectModifier() == null
                || c.getRedirectModifier() instanceof CustomModifierExecutor<?>) return null;
        var redirect = c.getRedirectModifier().getClass();
        if (!redirect.isSynthetic()
                || redirect.getNestHost() != net.minecraft.server.commands.ExecuteCommand.class)
            return null;
        List<String> names = ScoreAddPrototype.nodeNames(c);
        String input = text(c);
        if (first) {
            if (names.isEmpty() || !names.getFirst().equals("execute")
                    || !input.startsWith("execute ")) return null;
            names = names.subList(1, names.size());
            input = input.substring(8);
        }
        if (names.equals(List.of("as", "targets"))
                && input.startsWith("as @")
                && ScoreAddPrototype.extractNodeText(c, "targets").startsWith("@"))
            return Kind.AS;
        if (names.equals(List.of("at", "targets")) && input.equals("at @s")
                && "@s".equals(ScoreAddPrototype.extractNodeText(c, "targets")))
            return Kind.AT_SELF;
        if (names.size() >= 5 && (names.getFirst().equals("if") || names.getFirst().equals("unless"))
                && names.get(1).equals("score")
                && ScoreConditionCommand.typedIrLiteralGuardShape(
                        "execute " + input + " run scoreboard players add #ir048_shape dummy 1"))
            return Kind.SCORE;
        return null;
    }

    @SuppressWarnings("unchecked")
    static Plan lower(UnboundEntryAction<CommandSourceStack> original, Identifier id) {
        if (!ENABLED || !TypedScoreIR.enabledFor(id)
                || ProbeConfiguration.scoreAddPrototypeEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()
                || ProbeConfiguration.fusedRegionPrototypeEnabled()
                || ProbeConfiguration.bytecodeRegionPrototypeEnabled()
                || !(original instanceof BuildContexts.Unbound<?> unbound)) return null;
        var access = (BuildContextsAccessor<CommandSourceStack>) (Object) unbound;
        String input = access.functionCompiler$getCommandInput();
        if (input == null || !input.startsWith("execute ") || input.contains("$(")) return null;
        var chain = access.functionCompiler$getCommand();
        if (chain.getStage() == ContextChain.Stage.EXECUTE) return null;
        var parsed = (ContextChainAccessor<CommandSourceStack>) (Object) chain;
        var mods = parsed.functionCompiler$getModifiers();
        if (mods.size() != 3 && mods.size() != 4) return null;
        var run = mods.getLast();
        if (!ScoreAddPrototype.nodeNames(run).equals(List.of("run"))
                || run.isForked() || run.getRedirectModifier() != null) return null;
        List<CommandContext<CommandSourceStack>> stages = mods.subList(0, mods.size() - 1);
        List<Kind> kinds = new ArrayList<>(stages.size());
        List<String> texts = new ArrayList<>(mods.size() + 1);
        for (int i = 0; i < stages.size(); i++) {
            var kind = classify(stages.get(i), i == 0);
            if (kind == null) return null;
            kinds.add(kind);
            texts.add(text(stages.get(i)));
        }
        if (!kinds.equals(List.of(Kind.AS, Kind.AT_SELF))
                && !kinds.equals(List.of(Kind.SCORE, Kind.AS, Kind.AT_SELF))
                && !kinds.equals(List.of(Kind.AS, Kind.SCORE))) return null;
        while (chain.getStage() != ContextChain.Stage.EXECUTE) chain = chain.nextStage();
        var terminal = chain.getTopContext();
        String terminalText = text(terminal);
        if (terminal.isForked()
                || !ScoreAddPrototype.nodeNames(terminal).equals(List.of("function", "name"))
                || !TARGET.matcher(terminalText).matches()
                || !(terminal.getCommand() instanceof CustomCommandExecutor<?> executor)
                || executor.getClass().getNestHost() != net.minecraft.server.commands.FunctionCommand.class)
            return null;
        texts.add("run");
        texts.add(terminalText);
        if (!input.equals(String.join(" ", texts))) return null;
        if (DIAGNOSTICS) LOWERED.increment();
        return new Plan(original, input, stages, chain,
                (CustomCommandExecutor<CommandSourceStack>) executor);
    }

    static String diagnostics() {
        return " ir048_lowered=" + LOWERED.sum() + " ir048_entered=" + ENTERED.sum()
                + " ir048_empty=" + EMPTY.sum() + " ir048_single=" + SINGLE.sum()
                + " ir048_multi=" + MULTI.sum() + " ir048_fallbacks=" + FALLBACK.sum()
                + " ir048_debits=" + DEBITS.sum() + " ir048_empty_debits=" + EMPTY_DEBITS.sum()
                + " ir048_modifiers=" + MODIFIERS.sum() + " ir048_multi_stages=" + MULTI_STAGES.sum()
                + " ir048_terminals=" + TERMINALS.sum() + " ir048_errors=" + ERRORS.sum()
                + " ir048_limit_errors=" + LIMIT_ERRORS.sum();
    }
}
