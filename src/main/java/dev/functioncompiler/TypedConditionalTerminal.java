package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.ContextChainAccessor;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ChainModifiers;
import net.minecraft.commands.execution.CommandQueueEntry;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.CustomModifierExecutor;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.execution.tasks.ContinuationTask;
import net.minecraft.commands.execution.tasks.ExecuteCommand;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.ScoreboardCommand;
import net.minecraft.server.commands.TagCommand;

import java.util.Collection;
import java.util.List;
import java.util.concurrent.atomic.LongAdder;
import java.util.regex.Pattern;

/**
 * IR044: specialize single native conditional redirects with ordinary terminals.
 * The native predicate and terminal callbacks remain the authority. Lower only
 * their fixed single-stage control path; never cache a block, tag or score result.
 * Vanilla continuation/terminal charging and live world effects are preserved.
 */
final class TypedConditionalTerminal {
    private static final boolean ENABLED = Boolean.parseBoolean(
            System.getenv("FC_TYPED_IR_GUARD_TERMINAL"));
    private static final boolean DIAGNOSTICS = Boolean.parseBoolean(
            System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static final String POS = "(?:-?\\d+|~(?:-?\\d+)?)";
    private static final Pattern BLOCK = Pattern.compile("^(if|unless) block (" + POS
            + " " + POS + " " + POS + ") (#?[a-z0-9_.-]+:[a-z0-9_./-]+)$");
    private static final Pattern TAG = Pattern.compile("^tag @s (add|remove) ([a-zA-Z0-9_.+-]+)$");
    // An ordinary deterministic terminal useful for the no-entity CPU fixture;
    // score-only scoreboard commands remain on the existing IR path.
    private static final Pattern ADD = Pattern.compile(
            "^scoreboard players add (#[a-zA-Z0-9_.+\\-]+) ([a-zA-Z0-9_.+\\-]+) (\\d+)$");
    private static final LongAdder LOWERED = new LongAdder(), BLOCKS = new LongAdder(),
            SCORES = new LongAdder(), ENTERED = new LongAdder(), PASS = new LongAdder(),
            SKIP = new LongAdder(), FALLBACK = new LongAdder(), ERRORS = new LongAdder();

    private TypedConditionalTerminal() {}

    record Plan(UnboundEntryAction<CommandSourceStack> original, String input,
                CommandContext<CommandSourceStack> guard,
                ExecuteCommand<CommandSourceStack> terminal)
            implements UnboundEntryAction<CommandSourceStack> {
        @Override public void execute(CommandSourceStack source,
                                      ExecutionContext<CommandSourceStack> context, Frame frame) {
            if (DIAGNOSTICS) ENTERED.increment();
            // Do not change a traced or callback-bearing original action.
            if (context.tracer() != null || source.callback() != CommandResultCallback.EMPTY
                    || context.forkLimit() <= 1) {
                if (DIAGNOSTICS) FALLBACK.increment();
                original.execute(source, context, frame);
                return;
            }
            Collection<CommandSourceStack> sources;
            // Mapped native BuildContexts: one debit per non-null modifier,
            // then native runModifier with no-op consumer and forked=true.
            context.profiler().push(() -> input);
            try {
                context.incrementCost();
                sources = ContextChain.runModifier(guard, source, (c, success, result) -> {}, true);
                if (sources.size() >= context.forkLimit()) {
                    if (DIAGNOSTICS) ERRORS.increment();
                    source.handleError(BuildContexts.ERROR_FORK_LIMIT_REACHED.create(context.forkLimit()),
                            true, context.tracer());
                    return;
                }
            } catch (CommandSyntaxException error) {
                if (DIAGNOSTICS) ERRORS.increment();
                source.handleError(error, true, context.tracer());
                return;
            } finally {
                context.profiler().pop();
            }
            if (sources.isEmpty()) {
                if (DIAGNOSTICS) SKIP.increment();
                return;
            }
            if (DIAGNOSTICS) PASS.increment();
            // Same queue insertion as native ContinuationTask's singleton
            // case. The deferred native ExecuteCommand still charges the
            // terminal quota and handles callbacks, failure and feedback.
            if (sources.size() == 1) {
                context.queueNext(new CommandQueueEntry<>(frame,
                        terminal.bind(sources.iterator().next())));
            } else {
                // Defensive native scheduling of actual returned sources.
                // Never rerun a modifier after it was invoked.
                ContinuationTask.schedule(context, frame, List.copyOf(sources),
                        (f, s) -> new CommandQueueEntry<>(f, terminal.bind(s)));
            }
        }
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
        if (input == null || !input.startsWith("execute ")) return null;
        String[] halves = input.substring(8).split(" run ", -1);
        if (halves.length != 2) return null;
        var block = BLOCK.matcher(halves[0]);
        boolean blockGuard = block.matches();
        var tag = TAG.matcher(halves[1]);
        boolean tagTerminal = tag.matches();
        var add = ADD.matcher(halves[1]);
        if (!tagTerminal && !(blockGuard && add.matches())) return null;
        if (!blockGuard && !(halves[0].startsWith("if score ")
                || halves[0].startsWith("unless score "))) return null;
        var chain = access.functionCompiler$getCommand();
        if (chain.getStage() == ContextChain.Stage.EXECUTE) return null;
        var parsed = (ContextChainAccessor<CommandSourceStack>) (Object) chain;
        var modifiers = parsed.functionCompiler$getModifiers();
        if (modifiers.size() != 2) return null;
        var guard = modifiers.getFirst();
        var run = modifiers.getLast();
        if (!ScoreAddPrototype.nodeNames(run).equals(List.of("run"))
                || run.isForked() || run.getRedirectModifier() != null
                || !guard.isForked() || guard.getRedirectModifier() == null
                || guard.getRedirectModifier() instanceof CustomModifierExecutor<?>) return null;
        // Require the original vanilla redirect; decline modded replacements.
        var redirectClass = guard.getRedirectModifier().getClass();
        if (!redirectClass.isSynthetic()
                || redirectClass.getNestHost() != net.minecraft.server.commands.ExecuteCommand.class)
            return null;
        if (blockGuard) {
            var names = ScoreAddPrototype.nodeNames(guard);
            if (names.size() != 5 || !names.subList(0, 3).equals(
                    List.of("execute", block.group(1), "block"))) return null;
            // Argument text is only an identity check; no block predicate is
            // constructed by this parser. Native tag resolution stays live.
            if (!block.group(2).equals(guard.getNodes().get(3).getRange().get(guard.getInput()))
                    || !block.group(3).equals(guard.getNodes().get(4).getRange().get(guard.getInput())))
                return null;
        } else if (ScoreAddPrototype.parseDispatchPredicates(chain, new String[]{halves[0]}) == null) {
            return null;
        }
        var terminal = parsed.functionCompiler$getExecutable();
        if (terminal == null || terminal.isForked() || terminal.getCommand() == null
                || terminal.getCommand() instanceof CustomCommandExecutor<?>) return null;
        var callback = terminal.getCommand().getClass();
        var names = ScoreAddPrototype.nodeNames(terminal);
        if (!callback.isSynthetic()) return null;
        if (tagTerminal) {
            if (callback.getNestHost() != TagCommand.class || names.size() != 4
                    || !"tag".equals(names.getFirst()) || !tag.group(1).equals(names.get(2))
                    || !"@s".equals(terminal.getNodes().get(1).getRange().get(terminal.getInput()))
                    || !tag.group(2).equals(terminal.getNodes().get(3).getRange().get(terminal.getInput())))
                return null;
        } else {
            if (callback.getNestHost() != ScoreboardCommand.class
                    || !names.equals(List.of("scoreboard","players","add","targets","objective","score"))
                    || !add.group(1).equals(ScoreAddPrototype.extractNodeText(terminal,"targets"))
                    || !add.group(2).equals(ScoreAddPrototype.extractNodeText(terminal,"objective"))
                    || !add.group(3).equals(ScoreAddPrototype.extractNodeText(terminal,"score"))) return null;
        }
        if (DIAGNOSTICS) {
            LOWERED.increment();
            if (blockGuard) BLOCKS.increment(); else SCORES.increment();
        }
        return new Plan(original, input, guard,
                new ExecuteCommand<>(input, ChainModifiers.DEFAULT.setForked(), terminal));
    }

    static String diagnostics() {
        return " ir044_lowered=" + LOWERED.sum() + " ir044_block_lowered=" + BLOCKS.sum()
                + " ir044_score_lowered=" + SCORES.sum() + " ir044_entered=" + ENTERED.sum()
                + " ir044_pass=" + PASS.sum() + " ir044_skip=" + SKIP.sum()
                + " ir044_fallbacks=" + FALLBACK.sum() + " ir044_errors=" + ERRORS.sum();
    }
}
