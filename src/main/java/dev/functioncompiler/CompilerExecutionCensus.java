package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.CommandContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.LongAdder;
import java.util.stream.Collectors;

/**
 * Research-only, explicitly allowlisted event-window census.
 *
 * Entry counts measure calls to UnboundEntryAction.execute (a datapack line
 * reached), NOT downstream fork cardinality or successful command execution.
 * Ordinary Brigadier callback counts are separately observed at Command.run.
 * CustomCommandExecutor is never replaced; its callback count is unavailable.
 */
public final class CompilerExecutionCensus {
    private static final boolean REQUESTED =
            Boolean.parseBoolean(System.getenv("FC_COMPILER_EXEC_CENSUS"));
    private static final String NAMESPACE =
            System.getenv("FC_COMPILER_EXEC_CENSUS_NAMESPACE");
    private static final String TARGET_TEXT =
            System.getenv("FC_COMPILER_EXEC_CENSUS_FUNCTIONS");
    private static final Set<String> TARGETS = TARGET_TEXT == null ? Set.of()
            : Arrays.stream(TARGET_TEXT.split(","))
                    .map(String::trim).filter(s -> !s.isEmpty())
                    .collect(Collectors.toUnmodifiableSet());
    private static final boolean CONFIGURED = REQUESTED
            && NAMESPACE != null && !NAMESPACE.isBlank() && !TARGETS.isEmpty()
            && TARGETS.stream().allMatch(s -> s.startsWith(NAMESPACE + ":"));
    private static final int MAX_SITES = 1024;
    private static final int MAX_EXAMPLE_CHARS = 240;
    private static final ConcurrentMap<Key, Site> SITES = new ConcurrentHashMap<>();
    private static volatile boolean ACTIVE;
    private static long registrationOverflow;

    private record Key(String function, int lineIndex) {}

    private static final class Site {
        final Key key;
        final String example;
        final LongAdder entryReached = new LongAdder();
        final LongAdder ordinaryCallbacks = new LongAdder();
        volatile String terminalKind = "unknown";

        Site(Key key, String example) {
            this.key = key;
            this.example = example;
        }

        void kind(String kind) {
            if (terminalKind.equals("unknown")) {
                terminalKind = kind;
            } else if (!terminalKind.equals(kind)) {
                terminalKind = "mixed";
            }
        }
    }

    private CompilerExecutionCensus() {}

    public static boolean enabledFor(Identifier id) {
        return CONFIGURED && id != null && TARGETS.contains(id.toString());
    }

    @SuppressWarnings("unchecked")
    static <T extends ExecutionCommandSource<T>> InstantiatedFunction<T> instrument(
            InstantiatedFunction<T> original, Identifier functionId
    ) {
        if (!enabledFor(functionId) || original instanceof CountedInstantiation<?>) {
            return original;
        }
        List<UnboundEntryAction<T>> entries = new ArrayList<>(original.entries().size());
        int index = 0;
        for (UnboundEntryAction<T> entry : original.entries()) {
            String example = "<non-Brigadier-entry>";
            BuildContextsAccessor<T> accessor = null;
            if (entry instanceof BuildContexts.Unbound<?>) {
                accessor = (BuildContextsAccessor<T>) (Object) entry;
                example = accessor.functionCompiler$getCommandInput();
            }
            Key key = new Key(functionId.toString(), index++);
            Site site = site(key, example);
            if (site == null) {
                // Preserve the original action, but force a failure in the dump.
                entries.add(entry);
                continue;
            }
            if (accessor == null) {
                site.kind("non_brigadier");
            } else {
                ContextChain<T> chain = accessor.functionCompiler$getCommand();
                while (chain != null && chain.getStage() != ContextChain.Stage.EXECUTE) {
                    chain = chain.nextStage();
                }
                if (chain == null) {
                    site.kind("no_executable");
                } else {
                    CommandContext<T> terminal = chain.getTopContext();
                    Command<T> command = terminal.getCommand();
                    if (command == null) {
                        site.kind("no_callback");
                    } else if (command instanceof CustomCommandExecutor<?>) {
                        site.kind("custom_executor");
                    } else {
                        // After any existing ScoreAdd lowering: no change in parser
                        // eligibility/counters and never wrap a CustomCommandExecutor.
                        ((CommandContextAccessor<T>) (Object) terminal)
                                .functionCompiler$setCommand(new CallbackCount<>(command, site));
                        site.kind("ordinary_callback");
                    }
                }
            }
            entries.add((source, context, frame) -> {
                if (ACTIVE) {
                    site.entryReached.increment();
                }
                entry.execute(source, context, frame);
            });
        }
        return new CountedInstantiation<>(original, List.copyOf(entries));
    }

    private static Site site(Key key, String example) {
        Site old = SITES.get(key);
        if (old != null) {
            return old;
        }
        if (SITES.size() >= MAX_SITES) {
            registrationOverflow++;
            return null;
        }
        String text = example == null ? "" : example.replace('\n', ' ').replace('\r', ' ');
        if (text.length() > MAX_EXAMPLE_CHARS) {
            text = text.substring(0, MAX_EXAMPLE_CHARS);
        }
        return SITES.computeIfAbsent(key, k -> new Site(k, text));
    }

    private record CountedInstantiation<T extends ExecutionCommandSource<T>>(
            InstantiatedFunction<T> original,
            List<UnboundEntryAction<T>> entries
    ) implements InstantiatedFunction<T> {
        @Override
        public Identifier id() {
            return original.id();
        }
    }

    private record CallbackCount<T extends ExecutionCommandSource<T>>(
            Command<T> delegate, Site site
    ) implements Command<T> {
        @Override
        public int run(CommandContext<T> context) throws CommandSyntaxException {
            if (ACTIVE) {
                site.ordinaryCallbacks.increment();
            }
            return delegate.run(context);
        }
    }

    static int begin(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(Component.literal(
                    "FC_EXEC requires enabled=true, namespace, and explicit function allowlist"));
            return 0;
        }
        ACTIVE = false;
        for (Site site : SITES.values()) {
            site.entryReached.reset();
            site.ordinaryCallbacks.reset();
        }
        ACTIVE = true;
        source.sendSuccess(() -> Component.literal(
                "FC_EXEC started namespace=" + NAMESPACE + " sites=" + SITES.size()), false);
        return 1;
    }

    static int finish(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_EXEC was not active"));
            return 0;
        }
        ACTIVE = false; // stop counting before formatting/logging the output
        long entries = SITES.values().stream().mapToLong(s -> s.entryReached.sum()).sum();
        long callbacks = SITES.values().stream().mapToLong(s -> s.ordinaryCallbacks.sum()).sum();
        FunctionCompilerMod.LOGGER.info(
                "FC_EXEC_BEGIN namespace={} sites={} entries={} callbacks={} overflow={} targets={}",
                NAMESPACE, SITES.size(), entries, callbacks, registrationOverflow, TARGETS.size());
        SITES.entrySet().stream()
                .sorted(Comparator.comparing((Map.Entry<Key, Site> e) -> e.getKey().function())
                        .thenComparingInt(e -> e.getKey().lineIndex()))
                .forEach(entry -> {
                    Site site = entry.getValue();
                    FunctionCompilerMod.LOGGER.info(
                            "FC_EXEC_ROW function={} index={} entries={} callbacks={} kind={} input={}",
                            site.key.function(), site.key.lineIndex(),
                            site.entryReached.sum(), site.ordinaryCallbacks.sum(),
                            site.terminalKind, site.example);
                });
        FunctionCompilerMod.LOGGER.info(
                "FC_EXEC_END namespace={} sites={} entries={} callbacks={} overflow={}",
                NAMESPACE, SITES.size(), entries, callbacks, registrationOverflow);
        source.sendSuccess(() -> Component.literal(
                "FC_EXEC ended entries=" + entries + " callbacks=" + callbacks
                + " sites=" + SITES.size() + " overflow=" + registrationOverflow), false);
        return 1;
    }
}
