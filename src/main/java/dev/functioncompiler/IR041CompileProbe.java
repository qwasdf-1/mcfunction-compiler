package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;

/** Separate diagnostic-load measurement; never enabled in timed execution JVMs. */
final class IR041CompileProbe {
    private static final boolean ENABLED = Boolean.parseBoolean(System.getenv("FC_IR041_COMPILE_TIMING"));
    private IR041CompileProbe() {}
    static boolean enabledFor(Identifier id) {
        if (!ENABLED || id == null) return false;
        String publisher = System.getenv("FC_IR042_COMPILE_TARGET");
        if (publisher != null && !publisher.isBlank()
                && (id.getNamespace().equals("erb") || id.getNamespace().equals("erb_generated"))
                && publisher.equals(id.toString())) return true;
        if (!id.getNamespace().equals("fc_ir")) return false;
        return switch (id.getPath()) {
            case "ir017_ir040_perf", "ir017_ir040_perf_base",
                 "ir017_ir041_mixed", "ir017_ir041_mixed_base",
                 "ir017_ir042_interp" -> true;
            default -> false;
        };
    }
    static void validate(net.minecraft.commands.functions.CommandFunction<?> function) {
        ThreadMXBean clock = ManagementFactory.getThreadMXBean();
        long cpuStart = clock.isCurrentThreadCpuTimeSupported() && clock.isThreadCpuTimeEnabled()
                ? clock.getCurrentThreadCpuTime() : -1L;
        long start = System.nanoTime();
        ScoreAddPrototype.compile(function);
        long wall = System.nanoTime() - start;
        long cpu = cpuStart < 0 ? -1L : clock.getCurrentThreadCpuTime() - cpuStart;
        System.out.println("IR042_ADAPTER function=" + function.id()
                + " wall_ns=" + wall + " thread_cpu_ns=" + cpu);
    }
    static InstantiatedFunction<CommandSourceStack> compile(PlainTextFunction<CommandSourceStack> function) {
        ThreadMXBean clock = ManagementFactory.getThreadMXBean();
        long cpuStart = clock.isCurrentThreadCpuTimeSupported() && clock.isThreadCpuTimeEnabled()
                ? clock.getCurrentThreadCpuTime() : -1L;
        long start = System.nanoTime();
        var compiled = TypedScoreIR.compile(function);
        long wall = System.nanoTime() - start;
        long cpu = cpuStart < 0 ? -1L : clock.getCurrentThreadCpuTime() - cpuStart;
        System.out.println("IR041_COMPILE function=" + function.id() + " source_lines="
                + function.entries().size() + " wall_ns=" + wall + " thread_cpu_ns=" + cpu);
        return compiled;
    }
}
