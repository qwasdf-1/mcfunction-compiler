package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;

import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Disabled-by-default ASM prototype that unrolls an eligible interpreted
 * ScoreAdd region into JVM methods. Each emitted step calls the same semantic
 * bridge as the interpreter, preserving vanilla command, quota, trace, result,
 * and error handling while removing the interpreted region's list iterator.
 */
public final class BytecodeRegionPrototype {
    private static final AtomicLong GENERATED_CLASS_IDS = new AtomicLong();
    private static final List<WeakReference<Class<?>>> GENERATED_CLASSES = new ArrayList<>();
    private static final ConcurrentMap<Integer, MethodHandle> CONSTRUCTOR_CACHE =
            new ConcurrentHashMap<>();
    private static final String GENERATED_PACKAGE = "dev/functioncompiler/";
    private static final String GENERATED_CLASS_PREFIX = "BytecodeRegion$";

    private BytecodeRegionPrototype() {
    }

    public static InstantiatedFunction<CommandSourceStack> compile(
            PlainTextFunction<CommandSourceStack> original
    ) {
        if (ProbeConfiguration.bytecodeColdPolicyEnabled() && isStartupFunction(original.id())) {
            return FusedRegionPrototype.compile(original);
        }
        return FusedRegionPrototype.compile(original, BytecodeRegionPrototype::compileRegion);
    }

    private static boolean isStartupFunction(Identifier id) {
        if (id == null) {
            return false;
        }
        String path = id.getPath();
        return "load".equals(path) || path.endsWith("/load") || path.contains("init");
    }

    private static UnboundEntryAction<CommandSourceStack> compileRegion(
            List<FusedRegionPrototype.FusedCommand> commands
    ) {
        if (ProbeConfiguration.bytecodeColdPolicyEnabled() && commands.size() < 3) {
            return FusedRegionPrototype.createInterpretedRegion(commands);
        }

        try {
            if (ProbeConfiguration.bytecodeCompileFailureEnabled()) {
                throw new IllegalStateException("Forced bytecode prototype compile failure");
            }
            int threshold = ProbeConfiguration.bytecodeTieredThreshold();
            if (threshold > 1) {
                return new TieredRegionAction(commands, threshold);
            }
            return compileRegionNow(commands);
        } catch (RuntimeException | LinkageError failure) {
            ProbeMetrics.bytecodeRegionCompileFailed();
            throw failure;
        }
    }

    static UnboundEntryAction<CommandSourceStack> compileRegionNow(
            List<FusedRegionPrototype.FusedCommand> commands
    ) {
        UnboundEntryAction<CommandSourceStack> generated = generate(commands);
        ProbeMetrics.bytecodeRegionCompiled();
        return generated;
    }

    private static UnboundEntryAction<CommandSourceStack> generate(
            List<FusedRegionPrototype.FusedCommand> commands
    ) {
        if (commands.size() < 2) {
            throw new IllegalArgumentException("A bytecode region needs at least two commands");
        }

        MethodHandle constructor = CONSTRUCTOR_CACHE.computeIfAbsent(
                commands.size(),
                BytecodeRegionPrototype::createConstructor
        );
        Object[] commandArray = commands.toArray();

        try {
            Object action = constructor.invoke(commandArray);
            @SuppressWarnings("unchecked")
            UnboundEntryAction<CommandSourceStack> typed =
                    (UnboundEntryAction<CommandSourceStack>) action;
            return typed;
        } catch (Throwable failure) {
            if (failure instanceof Error error) {
                throw error;
            }
            if (failure instanceof RuntimeException runtimeException) {
                throw runtimeException;
            }
            throw new IllegalStateException("Could not instantiate emitted bytecode region", failure);
        }
    }

    private static MethodHandle createConstructor(int commandCount) {
        long classId = GENERATED_CLASS_IDS.incrementAndGet();
        String internalName = GENERATED_PACKAGE + GENERATED_CLASS_PREFIX + classId;
        byte[] classBytes = BytecodeRegionEmitter.emitClass(internalName, commandCount);
        ProbeMetrics.bytecodeClassBytesGenerated(classBytes.length);

        try {
            MethodHandles.Lookup hiddenLookup = MethodHandles.lookup().defineHiddenClass(
                    classBytes,
                    true,
                    MethodHandles.Lookup.ClassOption.NESTMATE
            );
            Class<?> clazz = hiddenLookup.lookupClass();
            registerGeneratedClass(clazz);
            return hiddenLookup.findConstructor(
                    clazz,
                    MethodType.methodType(void.class, Object[].class)
            );
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Could not define emitted bytecode region for count " + commandCount, exception);
        }
    }

    public static void clearConstructorCache() {
        CONSTRUCTOR_CACHE.clear();
    }

    static boolean executeStep(
            Object[] commands,
            int index,
            CommandSourceStack source,
            ExecutionContext<CommandSourceStack> context,
            Frame frame
    ) {
        return FusedRegionPrototype.executeCommand(
                (FusedRegionPrototype.FusedCommand) commands[index],
                source,
                context,
                frame
        );
    }

    static void beginExecution() {
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.bytecodeRegionExecuted();
        }
    }

    private static synchronized void registerGeneratedClass(Class<?> generatedClass) {
        GENERATED_CLASSES.add(new WeakReference<>(generatedClass));
    }

    public static synchronized int liveGeneratedClassCount() {
        GENERATED_CLASSES.removeIf(reference -> reference.get() == null);
        return GENERATED_CLASSES.size();
    }

    public static int generatedClassLoaderIdentity() {
        return System.identityHashCode(BytecodeRegionPrototype.class.getClassLoader());
    }
}
