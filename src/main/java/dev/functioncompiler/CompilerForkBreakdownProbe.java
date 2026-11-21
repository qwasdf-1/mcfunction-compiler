package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.ArrayDeque;
import java.util.Collection;
import java.util.Deque;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

/**
 * IR-021 RESEARCH ONLY. Exact original Blastback restore/job_tick source line.
 * Separates modifier work, selector resolution, per-entity source creation,
 * one-time continuation scheduling and LATER per-entity queue staging.
 *
 * No native command, selector, stage, frame, quota or callback is replaced.
 * All CPU time streams are inclusive; nested streams are NOT additive.
 */
public final class CompilerForkBreakdownProbe {
    private static final String MODE = System.getenv("FC_CPU021_MODE");
    private static final String NAMESPACE = System.getenv("FC_CPU021_NAMESPACE");
    private static final String ORIGINAL =
            "execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] "
            + "if score @s erb.job = #active erb.job "
            + "run scoreboard players set #needs_restore erb.tmp 1";
    private static final boolean CONFIGURED = "erb".equals(NAMESPACE)
            && ("plain".equals(MODE) || "empty".equals(MODE) || "timed".equals(MODE));
    private static final ThreadMXBean CLOCK = ManagementFactory.getThreadMXBean();

    private static final int BUILD = 0;
    private static final int AS = 1;
    private static final int SCORE = 2;
    private static final int OTHER = 3;
    private static final int SELECTOR = 4;
    private static final int WITH_ENTITY = 5;
    private static final int SCHEDULE = 6;
    private static final int CONTINUATION = 7;

    private static final Stream[] STREAMS = {
            new Stream("exact_build_contexts", 16),
            new Stream("modifier_execute_as", 16),
            new Stream("modifier_score_predicate", 128),
            new Stream("modifier_other", 16),
            new Stream("entity_selector_find", 16),
            new Stream("source_with_entity", 128),
            new Stream("continuation_initial_schedule", 16),
            new Stream("continuation_deferred_step", 128)
    };
    private static final class Stream {
        final String name;
        final int stride;
        final AtomicLong visits = new AtomicLong();
        final AtomicLong samples = new AtomicLong();
        final AtomicLong cpu = new AtomicLong();
        final AtomicLong invalid = new AtomicLong();
        final AtomicLong results = new AtomicLong();
        final AtomicLong maximumResult = new AtomicLong();
        Stream(String name, int stride) { this.name = name; this.stride = stride; }
        void reset() {
            visits.set(0); samples.set(0); cpu.set(0); invalid.set(0);
            results.set(0); maximumResult.set(0);
        }
        void result(int size) {
            if (size < 0) {
                invalid.incrementAndGet(); return;
            }
            results.addAndGet(size);
            maximumResult.accumulateAndGet(size, Math::max);
        }
        void sample(long ns) {
            if (ns < 0) invalid.incrementAndGet();
            else { samples.incrementAndGet(); cpu.addAndGet(ns); }
        }
    }

    private record Marker(int kind, long started) {}
    private static final class Scope {
        final Scope parent;
        final long buildStarted;
        final Deque<Marker> modifiers = new ArrayDeque<>();
        long selectorStarted = -1L;
        long sourceStarted = -1L;
        long scheduleStarted = -1L;
        boolean scheduling;
        Scope(Scope parent, long buildStarted) {
            this.parent=parent; this.buildStarted=buildStarted;
        }
        int currentModifier() {
            Marker top=modifiers.peekFirst();
            return top == null ? -1 : top.kind;
        }
    }
    private static final ThreadLocal<Scope> CURRENT = new ThreadLocal<>();
    private static volatile boolean ACTIVE;

    private CompilerForkBreakdownProbe() {}

    private static long now() { return CLOCK.getCurrentThreadCpuTime(); }
    private static long begin(int kind) {
        if (!ACTIVE) return -1L;
        Stream stream=STREAMS[kind];
        long order=stream.visits.incrementAndGet();
        if ("plain".equals(MODE) || order%stream.stride!=0) return -1L;
        if ("empty".equals(MODE)) {
            long start=now();
            stream.sample(now()-start);
            return -1L;
        }
        return now();
    }
    private static void end(int kind, long started) {
        if (started>=0) STREAMS[kind].sample(now()-started);
    }

    /** Source matching is exact and guarded by a distinct startup+window gate. */
    public static void buildStart(String input) {
        if (!ACTIVE || !CONFIGURED || !ORIGINAL.equals(input)) return;
        CURRENT.set(new Scope(CURRENT.get(),begin(BUILD)));
    }
    public static void buildEnd(String input) {
        if (!CONFIGURED || !ORIGINAL.equals(input)) return;
        Scope scope=CURRENT.get();
        if (scope==null) return;
        if (!scope.modifiers.isEmpty() || scope.scheduling
                || scope.selectorStarted>=0 || scope.sourceStarted>=0) {
            STREAMS[BUILD].invalid.incrementAndGet();
        }
        end(BUILD,scope.buildStarted);
        if(scope.parent==null) CURRENT.remove();
        else CURRENT.set(scope.parent);
    }

    private static int modifierKind(CommandContext<?> context) {
        boolean as=false, predicate=false, score=false;
        for(var parsed:context.getNodes()) {
            String node=parsed.getNode().getName();
            if ("as".equals(node)) as=true;
            if ("if".equals(node) || "unless".equals(node)) predicate=true;
            if ("score".equals(node)) score=true;
        }
        if(as) return AS;
        if(predicate && score) return SCORE;
        return OTHER;
    }
    public static void modifierStart(CommandContext<?> context) {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null) return;
        int kind=modifierKind(context);
        scope.modifiers.push(new Marker(kind,begin(kind)));
    }
    public static void modifierEnd(Collection<?> results) {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null) return;
        Marker marker=scope.modifiers.pollFirst();
        if (marker==null) { STREAMS[OTHER].invalid.incrementAndGet(); return; }
        STREAMS[marker.kind].result(results==null ? -1 : results.size());
        end(marker.kind,marker.started);
    }

    public static void selectorStart() {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null || scope.currentModifier()!=AS) return;
        if (scope.selectorStarted>=0) STREAMS[SELECTOR].invalid.incrementAndGet();
        scope.selectorStarted=begin(SELECTOR);
    }
    public static void selectorEnd(List<?> result) {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null || scope.currentModifier()!=AS) return;
        STREAMS[SELECTOR].result(result==null ? -1 : result.size());
        end(SELECTOR,scope.selectorStarted);
        scope.selectorStarted=-1L;
    }
    public static void entitySourceStart() {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null || scope.currentModifier()!=AS) return;
        if (scope.sourceStarted>=0) STREAMS[WITH_ENTITY].invalid.incrementAndGet();
        scope.sourceStarted=begin(WITH_ENTITY);
    }
    public static void entitySourceEnd() {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null || scope.currentModifier()!=AS) return;
        end(WITH_ENTITY,scope.sourceStarted);
        scope.sourceStarted=-1L;
    }

    /** The initial schedule may defer hundreds of individual queue insertions. */
    public static void scheduleStart(List<?> sources) {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null) return;
        if (scope.scheduling) { STREAMS[SCHEDULE].invalid.incrementAndGet(); return; }
        scope.scheduling=true;
        STREAMS[SCHEDULE].result(sources==null ? -1 : sources.size());
        scope.scheduleStarted=begin(SCHEDULE);
    }
    public static void scheduleEnd() {
        Scope scope=CURRENT.get();
        if (!ACTIVE || scope==null || !scope.scheduling) return;
        end(SCHEDULE,scope.scheduleStarted);
        scope.scheduleStarted=-1L;
        scope.scheduling=false;
    }
    /** Called from native ContinuationTask constructor; never tags ordinary tasks. */
    public static boolean continuationConstructedForTarget() {
        Scope scope=CURRENT.get();
        return ACTIVE && scope!=null && scope.scheduling;
    }
    /** Called for actual LATER native ContinuationTask.execute invocations. */
    public static long continuationStepStart(boolean marked) {
        return marked ? begin(CONTINUATION) : -1L;
    }
    public static void continuationStepEnd(boolean marked, long started) {
        if (marked) end(CONTINUATION,started);
    }

    public static int start(CommandSourceStack source) {
        if (!CONFIGURED) {
            source.sendFailure(Component.literal("FC_CPU021 requires erb + plain|empty|timed"));
            return 0;
        }
        if (!"plain".equals(MODE)) {
            if (!CLOCK.isCurrentThreadCpuTimeSupported()) {
                source.sendFailure(Component.literal("FC_CPU021 current thread CPU unsupported"));
                return 0;
            }
            if (!CLOCK.isThreadCpuTimeEnabled()) CLOCK.setThreadCpuTimeEnabled(true);
            if (now()<0) {
                source.sendFailure(Component.literal("FC_CPU021 current thread CPU unavailable"));
                return 0;
            }
        }
        ACTIVE=false;
        CURRENT.remove();
        for(Stream s:STREAMS) s.reset();
        ACTIVE=true;
        source.sendSuccess(()->Component.literal("FC_CPU021 started mode="+MODE),false);
        return 1;
    }
    public static int stop(CommandSourceStack source) {
        if (!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_CPU021 not active"));
            return 0;
        }
        ACTIVE=false;
        if (CURRENT.get()!=null) {
            STREAMS[BUILD].invalid.incrementAndGet();
            CURRENT.remove();
        }
        FunctionCompilerMod.LOGGER.info("FC_CPU021_BEGIN mode={}",MODE);
        for (Stream s:STREAMS) {
            FunctionCompilerMod.LOGGER.info(
                    "FC_CPU021_ROW kind={} stride={} visits={} samples={} cpu_ns={} invalid={} outputs={} max_outputs={}",
                    s.name,s.stride,s.visits.get(),s.samples.get(),
                    s.cpu.get(),s.invalid.get(),s.results.get(),s.maximumResult.get());
        }
        FunctionCompilerMod.LOGGER.info("FC_CPU021_END mode={}",MODE);
        source.sendSuccess(()->Component.literal("FC_CPU021 ended mode="+MODE),false);
        return 1;
    }
}
