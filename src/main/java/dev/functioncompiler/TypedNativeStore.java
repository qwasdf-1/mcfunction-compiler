package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.ContextChainAccessor;
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
import java.util.Collection;
import java.util.List;
import java.util.concurrent.atomic.LongAdder;
import java.util.regex.Pattern;

/**
 * IR045: specialize orchestration of a single parsed score-store redirect.
 * The original redirect creates the live native result callback. Neither
 * NBT access nor result/success storage is reimplemented. Never retain a
 * transformed source, objective, score, callback, or data accessor.
 */
final class TypedNativeStore {
    private static final boolean ENABLED = Boolean.parseBoolean(System.getenv("FC_TYPED_IR_NATIVE_STORE"));
    private static final boolean DIAGNOSTICS = Boolean.parseBoolean(System.getenv("FC_TYPED_IR_DIAGNOSTICS"));
    private static final String H = "(?:#[A-Za-z0-9_.+\\-]+|@s)";
    private static final String O = "[A-Za-z0-9_.+\\-]+";
    private static final String ID = "[a-z0-9_.-]+:[a-z0-9_./-]+";
    private static final Pattern STORE = Pattern.compile("^store (result|success) score ("+H+") ("+O+")$");
    private static final Pattern GET = Pattern.compile("^data get (?:entity @s Pos\\[[012]\\]|storage "+ID+" "+O+") 1$");
    private static final Pattern COPY = Pattern.compile("^data modify entity @s "+O+" set from block ~ ~ ~ \\{\\}$");
    private static final Pattern ADD = Pattern.compile("^scoreboard players add #[A-Za-z0-9_.+\\-]+ "+O+" [0-9]+$");
    private static final LongAdder LOWERED = new LongAdder(), DATA = new LongAdder(), SCORE = new LongAdder(),
            ENTERED = new LongAdder(), QUEUED = new LongAdder(), EMPTY = new LongAdder(),
            FALLBACK = new LongAdder(), ERRORS = new LongAdder();
    private TypedNativeStore() {}

    record Plan(UnboundEntryAction<CommandSourceStack> original, String input,
                CommandContext<CommandSourceStack> modifier,
                ExecuteCommand<CommandSourceStack> terminal, boolean forked)
            implements UnboundEntryAction<CommandSourceStack> {
        @Override public void execute(CommandSourceStack source,
                                      ExecutionContext<CommandSourceStack> context, Frame frame) {
            if (DIAGNOSTICS) ENTERED.increment();
            // Native trace and restrictive fork limits retain original path.
            // Existing callbacks are deliberately permitted: the original
            // redirect owns native callback composition, not this compiler.
            if (context.tracer() != null || context.forkLimit() <= 1) {
                if (DIAGNOSTICS) FALLBACK.increment();
                original.execute(source, context, frame);
                return;
            }
            Collection<CommandSourceStack> sources;
            context.profiler().push(() -> input);
            try {
                context.incrementCost();
                sources = ContextChain.runModifier(modifier, source, (c,s,r) -> {}, forked);
                if (sources.size() >= context.forkLimit()) {
                    if (DIAGNOSTICS) ERRORS.increment();
                    source.handleError(BuildContexts.ERROR_FORK_LIMIT_REACHED.create(context.forkLimit()),
                            forked, context.tracer());
                    return;
                }
            } catch (CommandSyntaxException failure) {
                if (DIAGNOSTICS) ERRORS.increment();
                source.handleError(failure, forked, context.tracer());
                return;
            } finally { context.profiler().pop(); }
            if (sources.isEmpty()) {
                if (DIAGNOSTICS) EMPTY.increment();
                return;
            }
            if (DIAGNOSTICS) QUEUED.increment();
            // Queue native ExecuteCommand; its own debit, source callback,
            // success/result/error handling and ordering remain untouched.
            if (sources.size() == 1) {
                context.queueNext(new CommandQueueEntry<>(frame,terminal.bind(sources.iterator().next())));
            } else {
                ContinuationTask.schedule(context,frame,List.copyOf(sources),
                        (f,s) -> new CommandQueueEntry<>(f,terminal.bind(s)));
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
        String[] parts = input.substring(8).split(" run ", -1);
        if (parts.length != 2) return null;
        var store = STORE.matcher(parts[0]);
        if (!store.matches()) return null;
        boolean data = GET.matcher(parts[1]).matches() || COPY.matcher(parts[1]).matches();
        if (!data && !ADD.matcher(parts[1]).matches()) return null;
        var chain = access.functionCompiler$getCommand();
        if (chain.getStage() == ContextChain.Stage.EXECUTE) return null;
        var parsed = (ContextChainAccessor<CommandSourceStack>) (Object) chain;
        var modifiers = parsed.functionCompiler$getModifiers();
        if (modifiers.size() != 2) return null;
        var mod = modifiers.getFirst();
        var run = modifiers.getLast();
        if (!ScoreAddPrototype.nodeNames(run).equals(List.of("run"))
                || run.isForked() || run.getRedirectModifier() != null
                || mod.getRedirectModifier() == null
                || mod.getRedirectModifier() instanceof CustomModifierExecutor<?>) return null;
        var names = ScoreAddPrototype.nodeNames(mod);
        if (!names.equals(List.of("execute","store",store.group(1),"score","targets","objective"))
                || !store.group(2).equals(ScoreAddPrototype.extractNodeText(mod,"targets"))
                || !store.group(3).equals(ScoreAddPrototype.extractNodeText(mod,"objective"))) return null;
        var terminal = parsed.functionCompiler$getExecutable();
        if (terminal == null || terminal.isForked() || terminal.getCommand() == null
                || terminal.getCommand() instanceof CustomCommandExecutor<?>) return null;
        // Match the entire original terminal node range, not a reparse or
        // substitute callback. DataCommands owns its nested callbacks.
        var nodes = terminal.getNodes();
        if (nodes.isEmpty() || !parts[1].equals(terminal.getInput().substring(
                nodes.getFirst().getRange().getStart(),nodes.getLast().getRange().getEnd()))) return null;
        var callback = terminal.getCommand().getClass();
        String host = callback.getNestHost().getName();
        if (!callback.isSynthetic() || !(data
                ? host.equals("net.minecraft.server.commands.data.DataCommands")
                : host.equals("net.minecraft.server.commands.ScoreboardCommand"))) return null;
        // Ordinary redirect is retained as-is, including its parsed fork bit;
        // no assertion about callback internals or transformed source identity.
        boolean forked = mod.isForked();
        if (DIAGNOSTICS) {
            LOWERED.increment();
            if (data) DATA.increment(); else SCORE.increment();
        }
        return new Plan(original,input,mod,new ExecuteCommand<>(input,
                forked ? ChainModifiers.DEFAULT.setForked() : ChainModifiers.DEFAULT,terminal),forked);
    }

    static String diagnostics() {
        return " ir045_lowered="+LOWERED.sum()+" ir045_data_lowered="+DATA.sum()
                +" ir045_score_lowered="+SCORE.sum()+" ir045_entered="+ENTERED.sum()
                +" ir045_queued="+QUEUED.sum()+" ir045_empty="+EMPTY.sum()
                +" ir045_fallbacks="+FALLBACK.sum()+" ir045_errors="+ERRORS.sum();
    }
}
