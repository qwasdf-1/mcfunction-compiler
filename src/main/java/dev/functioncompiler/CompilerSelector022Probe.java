package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.entity.EntityTypeTest;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Predicate;

/**
 * IR-022 RESEARCH ONLY. Exact original Blastback source's native selector:
 * outer selection, native getPredicate, typed world-entity gathering,
 * original EntityTypeTest.tryCast, original composite Predicate.test and
 * original sortAndLimit. All original callbacks are delegated exactly once.
 *
 * PLAIN / EMPTY / TIMED all use the SAME diagnostic wrappers. CONTROL
 * intentionally retains the original type and predicate object identities,
 * for an observer-off real-event reference. This is measurement, not
 * an optimization or proof that wrapper allocation is free.
 */
public final class CompilerSelector022Probe {
    private static final String MODE = System.getenv("FC_CPU022_MODE");
    private static final String NAMESPACE = System.getenv("FC_CPU022_NAMESPACE");
    private static final String ORIGINAL =
            "execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] "
            + "if score @s erb.job = #active erb.job "
            + "run scoreboard players set #needs_restore erb.tmp 1";
    private static final boolean CONFIGURED = "erb".equals(NAMESPACE)
            && ("control".equals(MODE) || "plain".equals(MODE)
            || "empty".equals(MODE) || "timed".equals(MODE));
    private static final ThreadMXBean CLOCK = ManagementFactory.getThreadMXBean();
    public static final int FIND = 0, MAKE_PREDICATE = 1, GATHER = 2,
            TYPE = 3, COMPOSITE = 4, SORT = 5;
    private static final Stream[] STREAMS = {
            new Stream("selector_find_entire",16),
            new Stream("selector_build_predicate",16),
            new Stream("selector_gather_entities",16),
            new Stream("native_type_try_cast",256),
            new Stream("native_composite_predicate",128),
            new Stream("selector_sort_and_limit",16)
    };
    private static final class Stream {
        final String name;
        final int stride;
        final AtomicLong visits=new AtomicLong();
        final AtomicLong samples=new AtomicLong();
        final AtomicLong cpuNs=new AtomicLong();
        final AtomicLong invalid=new AtomicLong();
        final AtomicLong passed=new AtomicLong();
        final AtomicLong resultCount=new AtomicLong();
        final AtomicLong maxResult=new AtomicLong();
        Stream(String name,int stride) {this.name=name;this.stride=stride;}
        void reset() {
            visits.set(0);samples.set(0);cpuNs.set(0);invalid.set(0);
            passed.set(0);resultCount.set(0);maxResult.set(0);
        }
        void output(int count) {
            if (count<0) {invalid.incrementAndGet();return;}
            resultCount.addAndGet(count);
            maxResult.accumulateAndGet(count,Math::max);
        }
        void sample(long delta) {
            if (delta<0) invalid.incrementAndGet();
            else {samples.incrementAndGet();cpuNs.addAndGet(delta);}
        }
    }
    private static final class Scope {
        final Scope parent;
        final boolean activeSelector;
        long findStarted=-1, predicateStarted=-1, gatherStarted=-1, sortStarted=-1;
        int gatherBefore=-1;
        Scope(Scope parent, boolean activeSelector) {
            this.parent=parent;
            this.activeSelector=activeSelector;
        }
    }
    private static final ThreadLocal<Scope> CURRENT=new ThreadLocal<>();
    private static volatile boolean ACTIVE;
    private CompilerSelector022Probe() {}

    private static long now() {return CLOCK.getCurrentThreadCpuTime();}
    private static long begin(int kind) {
        if (!ACTIVE) return -1L;
        Stream stream=STREAMS[kind];
        long visit=stream.visits.incrementAndGet();
        if ("control".equals(MODE)) return -1L;
        if ("plain".equals(MODE) || visit%stream.stride!=0) return -1L;
        if ("empty".equals(MODE)) {
            long before=now();
            stream.sample(now()-before);
            return -1L;
        }
        return now();
    }
    private static void end(int kind,long start) {
        if (start>=0L) STREAMS[kind].sample(now()-start);
    }
    private static Scope activeSelector() {
        Scope scope=CURRENT.get();
        return ACTIVE && scope!=null && scope.activeSelector ? scope:null;
    }

    /** Marks only the exact original BuildContexts command's synchronous scope. */
    public static void buildStart(String input) {
        if (!CONFIGURED || !ACTIVE || !ORIGINAL.equals(input)) return;
        CURRENT.set(new Scope(CURRENT.get(),false));
    }
    public static void buildEnd(String input) {
        if (!CONFIGURED || !ORIGINAL.equals(input)) return;
        Scope scope=CURRENT.get();
        if(scope==null || scope.activeSelector) {
            if(ACTIVE) STREAMS[FIND].invalid.incrementAndGet();
            return;
        }
        if(scope.parent==null) CURRENT.remove();
        else CURRENT.set(scope.parent);
    }
    public static void findStart() {
        Scope parent=CURRENT.get();
        if(!ACTIVE || parent==null) return;
        // A selector query nested inside the tagged original selector remains
        // uninstrumented; never attribute unrelated child lookups to Blastback.
        boolean selected=!parent.activeSelector;
        Scope child=new Scope(parent,selected);
        CURRENT.set(child);
        if(selected)child.findStarted=begin(FIND);
    }
    public static void findEnd(int count) {
        Scope child=CURRENT.get();
        if(!ACTIVE || child==null)return;
        if(!child.activeSelector) {
            // Nested unrelated selector calls must restore the exact parent
            // scope, even though we deliberately do not time their work.
            CURRENT.set(child.parent);
            return;
        }
        STREAMS[FIND].output(count);
        end(FIND,child.findStarted);
        if(child.predicateStarted>=0 || child.gatherStarted>=0 || child.sortStarted>=0)
            STREAMS[FIND].invalid.incrementAndGet();
        CURRENT.set(child.parent);
    }
    public static void predicateBuildStart() {
        Scope child=activeSelector();
        if(child!=null)child.predicateStarted=begin(MAKE_PREDICATE);
    }
    public static void predicateBuildEnd() {
        Scope child=activeSelector();
        if(child!=null) {
            end(MAKE_PREDICATE,child.predicateStarted);
            child.predicateStarted=-1;
        }
    }
    public static void gatherStart(int before) {
        Scope child=activeSelector();
        if(child!=null) {
            child.gatherBefore=before;
            child.gatherStarted=begin(GATHER);
        }
    }
    public static void gatherEnd(int after) {
        Scope child=activeSelector();
        if(child!=null) {
            STREAMS[GATHER].output(after-child.gatherBefore);
            end(GATHER,child.gatherStarted);
            child.gatherStarted=-1;
            child.gatherBefore=-1;
        }
    }
    public static void sortStart(int inputCount) {
        Scope child=activeSelector();
        if(child!=null) {
            STREAMS[SORT].output(inputCount);
            child.sortStarted=begin(SORT);
        }
    }
    public static void sortEnd(int returnedCount) {
        Scope child=activeSelector();
        if(child!=null) {
            STREAMS[SORT].passed.addAndGet(returnedCount);
            end(SORT,child.sortStarted);
            child.sortStarted=-1;
        }
    }
    private static boolean wrapEnabled() {
        return activeSelector()!=null && !"control".equals(MODE);
    }
    /**
     * Only replaces a diagnostic argument to ServerLevel.getEntities when
     * explicitly enabled. Delegates type tests and getBaseClass unchanged.
     * No selector entity or result-list values are edited.
     */
    public static <B,T extends B> EntityTypeTest<B,T> typeArgument(
            EntityTypeTest<B,T> original
    ) {
        if (!wrapEnabled()) return original;
        return new EntityTypeTest<B,T>() {
            @Override public T tryCast(B value) {
                long started=begin(TYPE);
                try {
                    T result=original.tryCast(value);
                    if (result!=null) STREAMS[TYPE].passed.incrementAndGet();
                    return result;
                } finally {
                    end(TYPE,started);
                }
            }
            @Override public Class<? extends B> getBaseClass() {
                return original.getBaseClass();
            }
        };
    }
    /**
     * Exact vanilla composite selector predicate: originally constructed by
     * EntitySelector.getPredicate (tag tests and feature/spatial checks).
     * We CANNOT infer independent tag rejections from this combined result.
     * The counting proxy delegates once and never re-evaluates a predicate.
     */
    public static <T> Predicate<T> predicateArgument(Predicate<T> original) {
        if(!wrapEnabled())return original;
        return entity -> {
            long started=begin(COMPOSITE);
            try {
                boolean accepted=original.test(entity);
                if(accepted) STREAMS[COMPOSITE].passed.incrementAndGet();
                return accepted;
            } finally {
                end(COMPOSITE,started);
            }
        };
    }
    public static int start(CommandSourceStack source) {
        if(!CONFIGURED) {
            source.sendFailure(Component.literal(
                    "FC_CPU022 requires erb + control|plain|empty|timed"));
            return 0;
        }
        if("empty".equals(MODE) || "timed".equals(MODE)) {
            if(!CLOCK.isCurrentThreadCpuTimeSupported()) {
                source.sendFailure(Component.literal("FC_CPU022 CPU clock unsupported"));
                return 0;
            }
            if(!CLOCK.isThreadCpuTimeEnabled()) CLOCK.setThreadCpuTimeEnabled(true);
            if(now()<0) {
                source.sendFailure(Component.literal("FC_CPU022 CPU clock unavailable"));
                return 0;
            }
        }
        ACTIVE=false; CURRENT.remove();
        for(Stream stream:STREAMS)stream.reset();
        ACTIVE=true;
        source.sendSuccess(()->Component.literal("FC_CPU022 started mode="+MODE),false);
        return 1;
    }
    public static int stop(CommandSourceStack source) {
        if(!CONFIGURED || !ACTIVE) {
            source.sendFailure(Component.literal("FC_CPU022 was not active"));
            return 0;
        }
        ACTIVE=false;
        if(CURRENT.get()!=null) {
            STREAMS[FIND].invalid.incrementAndGet();
            CURRENT.remove();
        }
        FunctionCompilerMod.LOGGER.info("FC_CPU022_BEGIN mode={}",MODE);
        for(Stream s:STREAMS)FunctionCompilerMod.LOGGER.info(
                "FC_CPU022_ROW kind={} stride={} visits={} samples={} cpu_ns={} invalid={} passed={} outputs={} max_outputs={}",
                s.name,s.stride,s.visits.get(),s.samples.get(),s.cpuNs.get(),
                s.invalid.get(),s.passed.get(),s.resultCount.get(),s.maxResult.get());
        FunctionCompilerMod.LOGGER.info("FC_CPU022_END mode={}",MODE);
        source.sendSuccess(()->Component.literal("FC_CPU022 ended mode="+MODE),false);
        return 1;
    }
}
