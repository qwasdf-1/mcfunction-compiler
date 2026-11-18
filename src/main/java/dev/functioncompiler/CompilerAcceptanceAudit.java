package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.util.Comparator;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.LongAdder;

/**
 * Opt-in compiler acceptance census. Counts parse/install outcomes, not runtime
 * execution or avoidable CPU. Does not intercept command execution.
 *
 * A namespace is required deliberately: setting the switch alone must not
 * instrument arbitrary datapacks in a normal server process.
 */
public final class CompilerAcceptanceAudit {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_COMPILER_ACCEPTANCE_AUDIT"));
    private static final String NAMESPACE = System.getenv("FC_COMPILER_ACCEPTANCE_NAMESPACE");
    private static final int MAX_KEYS = 16384;
    private static final int MAX_INPUT_CHARS = 240;
    private static final ConcurrentMap<Key, LongAdder> COUNTS = new ConcurrentHashMap<>();

    private record Key(String functionId, String outcome, String input) {}

    private CompilerAcceptanceAudit() {}

    public static boolean enabledFor(Identifier functionId) {
        return ENABLED && NAMESPACE != null && !NAMESPACE.isBlank()
                && functionId != null && NAMESPACE.equals(functionId.getNamespace());
    }

    static void record(Identifier functionId, String outcome, String input) {
        if (!enabledFor(functionId)) {
            return;
        }
        String excerpt = input == null ? "" : input.replace('\n', ' ').replace('\r', ' ');
        if (excerpt.length() > MAX_INPUT_CHARS) {
            excerpt = excerpt.substring(0, MAX_INPUT_CHARS);
        }
        Key key = new Key(functionId.toString(), outcome, excerpt);
        if (!COUNTS.containsKey(key) && COUNTS.size() >= MAX_KEYS) {
            key = new Key("<overflow>", "bounded-key-overflow", "");
        }
        COUNTS.computeIfAbsent(key, ignored -> new LongAdder()).increment();
    }

    /** Dumps a machine-parseable, bounded report to the server log on request. */
    static int report(CommandSourceStack source) {
        if (!ENABLED || NAMESPACE == null || NAMESPACE.isBlank()) {
            source.sendFailure(Component.literal(
                    "FC_ACCEPTANCE disabled (requires both audit=true and namespace)"));
            return 0;
        }

        long total = COUNTS.values().stream().mapToLong(LongAdder::sum).sum();
        FunctionCompilerMod.LOGGER.info(
                "FC_ACCEPTANCE_BEGIN namespace={} events={} keys={} score_add={} fused={} selective_macros={}",
                NAMESPACE, total, COUNTS.size(),
                ProbeConfiguration.scoreAddPrototypeEnabled(),
                ProbeConfiguration.fusedRegionPrototypeEnabled(),
                ProbeConfiguration.selectiveMacroArgumentsEnabled());
        COUNTS.entrySet().stream()
                .sorted(Comparator.comparing((Map.Entry<Key, LongAdder> entry) ->
                        entry.getKey().functionId())
                        .thenComparing(entry -> entry.getKey().outcome())
                        .thenComparing(entry -> entry.getKey().input()))
                .forEach(entry -> FunctionCompilerMod.LOGGER.info(
                        "FC_ACCEPTANCE_ROW function={} outcome={} count={} input={}",
                        entry.getKey().functionId(), entry.getKey().outcome(),
                        entry.getValue().sum(), entry.getKey().input()));
        FunctionCompilerMod.LOGGER.info("FC_ACCEPTANCE_END namespace={} events={}", NAMESPACE, total);
        source.sendSuccess(() -> Component.literal(
                "FC_ACCEPTANCE entries=" + COUNTS.size() + " events=" + total
                        + " (full census written to server log)"), false);
        return 1;
    }
}
