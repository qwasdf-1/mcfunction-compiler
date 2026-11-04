package dev.functioncompiler;

import java.util.Locale;
import java.util.Map;

/**
 * Emits one consolidated datapack coverage report per successful reload.
 *
 * Functions are grouped by namespace, which is the practical grouping for a
 * datapack: a pack normally owns a single namespace, so the per-namespace rows
 * read as "datapack N: X functions, Y% covered". When two packs deliberately
 * share a namespace their functions are reported together; the aggregate row is
 * unaffected. The report is deliberately emitted once, from
 * {@code ServerFunctionManager.replaceLibrary}, rather than per function, so it
 * never floods the log during a load with thousands of functions.
 */
public final class FunctionCoverageReport {
    private FunctionCoverageReport() {
    }

    public static void logReloadReport() {
        Map<String, Long> loaded = ProbeMetrics.functionsByNamespace();
        Map<String, Long> covered = ProbeMetrics.coveredFunctionsByNamespace();
        long totalLoaded = loaded.values().stream().mapToLong(Long::longValue).sum();
        long totalCovered = covered.values().stream().mapToLong(Long::longValue).sum();
        double overallPercent = percent(totalCovered, totalLoaded);

        FunctionCompilerMod.LOGGER.info(
                "Function coverage: {} functions loaded, {} covered ({}), {} namespace(s)",
                totalLoaded,
                totalCovered,
                formatPercent(overallPercent),
                loaded.size()
        );
        if (loaded.isEmpty()) {
            FunctionCompilerMod.LOGGER.info("Function coverage: no functions were loaded");
            return;
        }
        for (Map.Entry<String, Long> entry : loaded.entrySet()) {
            String namespace = entry.getKey();
            long count = entry.getValue();
            long coveredInNamespace = covered.getOrDefault(namespace, 0L);
            FunctionCompilerMod.LOGGER.info(
                    "Function coverage: namespace {} -> {} functions, {} covered ({})",
                    namespace,
                    count,
                    coveredInNamespace,
                    formatPercent(percent(coveredInNamespace, count))
            );
        }
        // Reset so a later reload rebuilds the report from its own function set.
        ProbeMetrics.resetCoverageCounters();
    }

    private static double percent(long covered, long loaded) {
        if (loaded == 0L) {
            return 0.0;
        }
        return covered * 100.0 / loaded;
    }

    private static String formatPercent(double value) {
        return String.format(Locale.ROOT, "%.1f%%", value);
    }
}
