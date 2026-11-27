package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;

import java.util.ArrayDeque;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.IdentityHashMap;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.resources.Identifier;

/** Fixture-only source-position native dispatch observation. No timing or command mutation. */
public final class IR048DispatchCensus {
    private static final String INPUTS = System.getenv("FC_IR048_CENSUS_SITES");
    private record Key(String function, int index) {}
    private static final Map<Key, Site> SITES = new LinkedHashMap<>();
    private static final Map<Object, Site> ENTRIES = new IdentityHashMap<>();
    private static long registrationErrors;
    static {
        if (INPUTS != null && !INPUTS.isBlank()) {
            for (String line : INPUTS.lines().toList()) {
                String[] parts = line.split("\t", 3);
                if (parts.length != 3 || SITES.size() >= 32) {
                    registrationErrors++;
                    continue;
                }
                Key key = new Key(parts[0], Integer.parseInt(parts[1]));
                if (SITES.containsKey(key) || key.index < 0 || parts[2].isBlank()) {
                    registrationErrors++;
                    continue;
                }
                SITES.put(key, new Site(SITES.size(), parts[2]));
            }
        }
    }
    private static final ThreadLocal<ArrayDeque<Scope>> SCOPES =
            ThreadLocal.withInitial(ArrayDeque::new);
    private static volatile boolean active;
    private static long invalid;
    private record Scope(Site site) {}
    private static final class Site {
        final int id;
        final String input;
        Object entry;
        long builds, customTerminals;
        final Map<String, Stage> stages = new LinkedHashMap<>();
        Site(int id, String input) { this.id = id; this.input = input; }
    }
    private static final class Stage {
        long calls, returns, outputs, maxOutputs, forkedCalls;
    }

    private IR048DispatchCensus() {}

    /** Function construction may occur on reload worker threads. Register only
     * the seven configured source positions; never mutate the actual entry. */
    public static synchronized void register(Identifier id, CommandFunction<?> built) {
        for (var item : SITES.entrySet()) {
            Key key = item.getKey();
            if (!key.function.equals(id.toString())) continue;
            Site site = item.getValue();
            if (active || !(built instanceof PlainTextFunction<?> plain)
                    || key.index >= plain.entries().size()) {
                registrationErrors++;
                continue;
            }
            Object entry = plain.entries().get(key.index);
            if (!(entry instanceof BuildContexts.Unbound<?>)) {
                registrationErrors++;
                continue;
            }
            var accessor = (BuildContextsAccessor<?>) entry;
            if (!site.input.equals(accessor.functionCompiler$getCommandInput())) {
                registrationErrors++;
                continue;
            }
            var chain = accessor.functionCompiler$getCommand();
            while (chain.getStage() != com.mojang.brigadier.context.ContextChain.Stage.EXECUTE)
                chain = chain.nextStage();
            if (!(chain.getTopContext().getCommand() instanceof CustomCommandExecutor<?>)) {
                registrationErrors++;
                continue;
            }
            if (ENTRIES.containsKey(entry) && ENTRIES.get(entry) != site) {
                registrationErrors++;
                continue;
            }
            if (site.entry != null) ENTRIES.remove(site.entry);
            site.entry = entry;
            ENTRIES.put(entry, site);
        }
    }

    public static synchronized int start(CommandSourceStack source) {
        if (active || SITES.isEmpty() || registrationErrors != 0 || ENTRIES.size() != SITES.size()) {
            source.sendFailure(Component.literal("IR048 incomplete source-position registration: sites="
                    + SITES.size() + " entries=" + ENTRIES.size() + " errors=" + registrationErrors));
            return 0;
        }
        SCOPES.remove();
        invalid = 0;
        for (var item : SITES.entrySet()) {
            Site site = item.getValue();
            site.builds = site.customTerminals = 0;
            site.stages.clear();
            FunctionCompilerMod.LOGGER.info("IR048_REGISTER id={} function={} index={}",
                    site.id, item.getKey().function, item.getKey().index);
        }
        active = true;
        source.sendSuccess(() -> Component.literal("FC_EXEC started ir048"), false);
        return 1;
    }

    private static synchronized Site siteFor(Object entry) {
        return ENTRIES.get(entry);
    }

    public static void buildStart(Object entry) {
        if (!active) return;
        Site site = siteFor(entry);
        SCOPES.get().push(new Scope(site));
        if (site != null) site.builds++;
    }

    public static void buildEnd(Object entry) {
        if (!active) return;
        Scope scope = SCOPES.get().poll();
        if (scope == null || scope.site != siteFor(entry)) invalid++;
        if (SCOPES.get().isEmpty()) SCOPES.remove();
    }

    private static Site current() {
        if (!active) return null;
        Scope scope = SCOPES.get().peek();
        return scope == null ? null : scope.site;
    }

    private static String key(CommandContext<?> context) {
        return String.join("/", context.getNodes().stream()
                .map(n -> n.getNode().getName()).toList());
    }

    public static void modifierStart(CommandContext<?> context, boolean forked) {
        Site site = current();
        if (site == null) return;
        Stage stage = site.stages.computeIfAbsent(key(context), k -> new Stage());
        stage.calls++;
        if (forked) stage.forkedCalls++;
    }

    public static void modifierReturn(CommandContext<?> context, Collection<?> result) {
        Site site = current();
        if (site == null) return;
        Stage stage = site.stages.get(key(context));
        if (stage == null || result == null) { invalid++; return; }
        stage.returns++;
        stage.outputs += result.size();
        stage.maxOutputs = Math.max(stage.maxOutputs, result.size());
    }

    public static void customTerminal() {
        Site site = current();
        if (site != null) site.customTerminals++;
    }

    public static synchronized int stop(CommandSourceStack source) {
        if (!active) {
            source.sendFailure(Component.literal("IR048 census not active"));
            return 0;
        }
        active = false;
        if (!SCOPES.get().isEmpty()) invalid++;
        invalid += registrationErrors;
        SCOPES.remove();
        FunctionCompilerMod.LOGGER.info("IR048_CENSUS_BEGIN");
        for (Site site : SITES.values()) {
            FunctionCompilerMod.LOGGER.info("IR048_SITE id={} builds={} terminals={}",
                    site.id, site.builds, site.customTerminals);
            for (var entry : site.stages.entrySet()) {
                Stage s = entry.getValue();
                FunctionCompilerMod.LOGGER.info(
                        "IR048_STAGE id={} key={} calls={} returns={} outputs={} max_outputs={} forked_calls={}",
                        site.id, entry.getKey(), s.calls, s.returns, s.outputs, s.maxOutputs, s.forkedCalls);
            }
        }
        FunctionCompilerMod.LOGGER.info("IR048_CENSUS_END invalid={}", invalid);
        source.sendSuccess(() -> Component.literal("FC_EXEC ended ir048 overflow=" + invalid), false);
        return invalid == 0 ? 1 : 0;
    }
}
