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
    // IR-019: independent allowlist of native child-function call task IDs.
    // A child can have multiple call sites; these counts NEVER claim a
    // one-to-one association with an individual guard or caller line.
    private static final String CALLEE_TEXT =
            System.getenv("FC_COMPILER_EXEC_CENSUS_CALLEES");
    private static final Set<String> CALLEES = CALLEE_TEXT == null ? Set.of()
            : Arrays.stream(CALLEE_TEXT.split(","))
                    .map(String::trim).filter(s -> !s.isEmpty())
                    .collect(Collectors.toUnmodifiableSet());
    private static final int MAX_CALLEE_IDS = 96;
    private static final boolean CALLEES_VALID = CALLEES.size() <= MAX_CALLEE_IDS
            && CALLEES.stream().allMatch(s ->
                    s.matches("[a-z0-9_.-]+:[a-z0-9_./-]+"));
    private static final ConcurrentMap<String, LongAdder> NATIVE_CALLS =
            new ConcurrentHashMap<>();
    private static final java.util.regex.Pattern SIMPLE_SCORE_DISPATCH =
            java.util.regex.Pattern.compile(
                    "^execute (?:if|unless) score (?:#[A-Za-z0-9_.+\\-]+|@s) "
                    + "[A-Za-z0-9_.+\\-]+ matches "
                    + "(?:-?\\d+(?:\\.\\.(?:-?\\d+)?)?|\\.\\.-?\\d+) "
                    + "run function [a-z0-9_.-]+:[a-z0-9_./-]+$");
    private static final java.util.regex.Pattern BROAD_SCORE_DISPATCH =
            java.util.regex.Pattern.compile(
                    "^execute (?:if|unless) score .+ run (?:return run )?function .+$");
    private static String dispatchShape(String input) {
        if (input == null || !BROAD_SCORE_DISPATCH.matcher(input).matches()) return "none";
        return SIMPLE_SCORE_DISPATCH.matcher(input).matches()
                ? "single_score_static_call" : "complex_or_return_call";
    }
    private static final boolean CONFIGURED = REQUESTED
            && NAMESPACE != null && !NAMESPACE.isBlank() && !TARGETS.isEmpty()
            && TARGETS.stream().allMatch(s -> s.startsWith(NAMESPACE + ":")
                    || (Boolean.parseBoolean(System.getenv("FC_IR042_BLASTBACK_CENSUS"))
                        && NAMESPACE.equals("erb") && s.startsWith("erb_generated:")))
            && CALLEES_VALID;
    private static final int MAX_SITES = 1024;
    private static final int MAX_EXAMPLE_CHARS = 240;
    private static final ConcurrentMap<Key, Site> SITES = new ConcurrentHashMap<>();
    private static volatile boolean ACTIVE;
    private static long registrationOverflow;

    private record Key(String function, int lineIndex) {}

    private static final class Site {
        final Key key;
        final String example;
        final String dispatchShape;
        final LongAdder entryReached = new LongAdder();
        final LongAdder ordinaryCallbacks = new LongAdder();
        volatile String terminalKind = "unknown";

        Site(Key key, String example) {
            this.key = key;
            this.example = example;
            this.dispatchShape = CompilerExecutionCensus.dispatchShape(example);
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

    /**
     * IR-019 passive observation at the original CallFunction task boundary.
     * Counts a native call task reached, NOT a child body completion, a
     * successful specific conditional guard, or one caller/source site.
     */
    public static void recordNativeCall(Identifier id) {
        if (!ACTIVE || !CONFIGURED || id == null) return;
        String key = id.toString();
        if (!CALLEES.contains(key)) return;
        LongAdder counter = NATIVE_CALLS.get(key);
        if (counter != null) counter.increment();
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
        final String sample = text;
        return SITES.computeIfAbsent(key, k -> new Site(k, sample));
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
        NATIVE_CALLS.clear();
        for (String target : CALLEES) {
            NATIVE_CALLS.put(target, new LongAdder());
        }
        ACTIVE = true;
        source.sendSuccess(() -> Component.literal(
                "FC_EXEC started namespace=" + NAMESPACE
                        + " sites=" + SITES.size()
                        + " callees=" + CALLEES.size()), false);
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
        long nativeCalls = NATIVE_CALLS.values().stream().mapToLong(LongAdder::sum).sum();
        long singleSourceEntries = SITES.values().stream()
                .filter(s -> s.dispatchShape.equals("single_score_static_call"))
                .mapToLong(s -> s.entryReached.sum()).sum();
        long complexSourceEntries = SITES.values().stream()
                .filter(s -> s.dispatchShape.equals("complex_or_return_call"))
                .mapToLong(s -> s.entryReached.sum()).sum();
        FunctionCompilerMod.LOGGER.info(
                "FC_EXEC_BEGIN namespace={} sites={} entries={} callbacks={} overflow={} targets={} callees={} native_calls={} single_dispatch_entries={} complex_dispatch_entries={}",
                NAMESPACE, SITES.size(), entries, callbacks,
                registrationOverflow, TARGETS.size(), CALLEES.size(),
                nativeCalls, singleSourceEntries, complexSourceEntries);
        SITES.entrySet().stream()
                .sorted(Comparator.comparing((Map.Entry<Key, Site> e) -> e.getKey().function())
                        .thenComparingInt(e -> e.getKey().lineIndex()))
                .forEach(entry -> {
                    Site site = entry.getValue();
                    FunctionCompilerMod.LOGGER.info(
                            "FC_EXEC_ROW function={} index={} entries={} callbacks={} kind={} dispatch_shape={} input={}",
                            site.key.function(), site.key.lineIndex(),
                            site.entryReached.sum(), site.ordinaryCallbacks.sum(),
                            site.terminalKind, site.dispatchShape, site.example);
                });
        NATIVE_CALLS.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> FunctionCompilerMod.LOGGER.info(
                        "FC_EXEC_CALLEE function={} native_call_tasks={}",
                        entry.getKey(), entry.getValue().sum()));
        FunctionCompilerMod.LOGGER.info(
                "FC_EXEC_END namespace={} sites={} entries={} callbacks={} overflow={} native_calls={} single_dispatch_entries={} complex_dispatch_entries={}",
                NAMESPACE, SITES.size(), entries, callbacks,
                registrationOverflow, nativeCalls, singleSourceEntries,
                complexSourceEntries);
        source.sendSuccess(() -> Component.literal(
                "FC_EXEC ended entries=" + entries + " callbacks=" + callbacks
                        + " sites=" + SITES.size() + " overflow=" + registrationOverflow
                        + " native_calls=" + nativeCalls
                        + " single_dispatch_entries=" + singleSourceEntries
                        + " complex_dispatch_entries=" + complexSourceEntries), false);
        return 1;
    }
}
