package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;

import java.util.ArrayDeque;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;

/** Fixture-only exact-input native dispatch observation. No timing, no mutation of commands. */
public final class IR048DispatchCensus {
    private static final String INPUTS = System.getenv("FC_IR048_CENSUS_INPUTS");
    private static final Map<String, Site> SITES = new LinkedHashMap<>();
    private static final ThreadLocal<ArrayDeque<Scope>> SCOPES =
            ThreadLocal.withInitial(ArrayDeque::new);
    private static boolean active;
    private static long invalid;
    private record Scope(Site site) {}
    private static final class Site {
        final int id;
        long builds, customTerminals;
        final Map<String, Stage> stages = new LinkedHashMap<>();
        Site(int id) { this.id = id; }
    }
    private static final class Stage {
        long calls, returns, outputs, maxOutputs, forkedCalls;
    }

    private IR048DispatchCensus() {}

    public static int start(CommandSourceStack source) {
        if (active || INPUTS == null || INPUTS.isBlank()) {
            source.sendFailure(Component.literal("IR048 census not configured or already active"));
            return 0;
        }
        SITES.clear();
        SCOPES.remove();
        invalid = 0;
        for (String input : INPUTS.lines().toList()) {
            if (input.isBlank() || SITES.containsKey(input) || SITES.size() >= 32) {
                source.sendFailure(Component.literal("IR048 invalid exact-input scope"));
                return 0;
            }
            SITES.put(input, new Site(SITES.size()));
        }
        active = true;
        source.sendSuccess(() -> Component.literal("FC_EXEC started ir048"), false);
        return 1;
    }

    public static void buildStart(String input) {
        if (!active) return;
        Site site = SITES.get(input);
        SCOPES.get().push(new Scope(site));
        if (site != null) site.builds++;
    }

    public static void buildEnd(String input) {
        if (!active) return;
        Scope scope = SCOPES.get().poll();
        if (scope == null || scope.site != SITES.get(input)) invalid++;
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

    public static int stop(CommandSourceStack source) {
        if (!active) {
            source.sendFailure(Component.literal("IR048 census not active"));
            return 0;
        }
        active = false;
        if (!SCOPES.get().isEmpty()) invalid++;
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
