package dev.functioncompiler;

import com.mojang.brigadier.CommandDispatcher;
import net.minecraft.commands.FunctionInstantiationException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.commands.functions.MacroFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.Identifier;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ProbeFunctionWrapper<T extends ExecutionCommandSource<T>> implements CommandFunction<T> {
    private final CommandFunction<T> delegate;
    private final InstantiatedFunction<T> compiledInstantiation;
    private final Map<List<String>, InstantiatedFunction<T>> parameterizedMacroCache =
            Collections.synchronizedMap(new LinkedHashMap<>(64, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<List<String>, InstantiatedFunction<T>> eldest) {
                    return size() > 256;
                }
            });
    private final Map<PlainTextFunction<?>, InstantiatedFunction<T>> macroCompilationCache =
            Collections.synchronizedMap(new LinkedHashMap<>(16, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<PlainTextFunction<?>, InstantiatedFunction<T>> eldest) {
                    return size() > 16;
                }
            });

    @SuppressWarnings("unchecked")
    public ProbeFunctionWrapper(CommandFunction<T> delegate) {
        this.delegate = delegate;
        ProbeMetrics.wrapperCreated();
        boolean excluded = delegate.id() != null
                && ProbeConfiguration.isNamespaceExcluded(delegate.id().getNamespace());
        boolean fuseThisFunction = !excluded && ProbeConfiguration.fusedRegionForFunction(delegate.id());
        if (!excluded && (ProbeConfiguration.scoreAddPrototypeEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()
                || ProbeConfiguration.fusedRegionPrototypeEnabled()
                || ProbeConfiguration.bytecodeRegionPrototypeEnabled())) {
            if (Boolean.parseBoolean(System.getenv("FC_BENCH_COMPILE_TIMING"))) {
                long started = System.nanoTime();
                try {
                    ScoreAddPrototype.compile(delegate);
                } finally {
                    ProbeMetrics.compileWallTime(delegate.id(), false, System.nanoTime() - started);
                }
            } else {
                ScoreAddPrototype.compile(delegate);
            }
        }
        if (!excluded && (fuseThisFunction
                || ProbeConfiguration.bytecodeRegionPrototypeEnabled())
                && delegate instanceof PlainTextFunction<?> plainTextFunction) {
            PlainTextFunction<CommandSourceStack> typedFunction =
                    (PlainTextFunction<CommandSourceStack>) plainTextFunction;
            InstantiatedFunction<CommandSourceStack> compiled;
            if (fuseThisFunction && !ProbeConfiguration.bytecodeRegionPrototypeEnabled()
                    && Boolean.parseBoolean(System.getenv("FC_BENCH_COMPILE_TIMING"))) {
                long started = System.nanoTime();
                try {
                    compiled = FusedRegionPrototype.compile(typedFunction);
                } finally {
                    ProbeMetrics.compileWallTime(delegate.id(), true, System.nanoTime() - started);
                }
            } else {
                compiled = ProbeConfiguration.bytecodeRegionPrototypeEnabled()
                        ? BytecodeRegionPrototype.compile(typedFunction)
                        : FusedRegionPrototype.compile(typedFunction);
            }
            compiledInstantiation = (InstantiatedFunction<T>) compiled;
        } else {
            compiledInstantiation = null;
        }
        if (!excluded && ProbeConfiguration.commandCallbackMetricsEnabled()) {
            CommandCallbackMetricPrototype.compile(delegate);
        }
    }

    public CommandFunction<T> delegate() {
        return delegate;
    }

    @Override
    public Identifier id() {
        return delegate.id();
    }

    @Override
    public InstantiatedFunction<T> instantiate(
            CompoundTag arguments,
            CommandDispatcher<T> dispatcher
    ) throws FunctionInstantiationException {
        ProbeMetrics.wrapperInstantiated();
        if (compiledInstantiation != null) {
            return compiledInstantiation;
        }
        if (delegate instanceof MacroFunction<?> macro) {
            List<String> argValues = MacroTemplateCompiler.extractArguments(macro, arguments);
            if (argValues != null) {
                InstantiatedFunction<T> cached = parameterizedMacroCache.get(argValues);
                if (cached != null) {
                    return cached;
                }
            }
            InstantiatedFunction<T> instantiated = delegate.instantiate(arguments, dispatcher);
            if (isEligibleMacro(instantiated)) {
                InstantiatedFunction<T> compiled = specializeMacro((PlainTextFunction<?>) instantiated);
                if (argValues != null) {
                    parameterizedMacroCache.put(argValues, compiled);
                }
                return compiled;
            }
            return instantiated;
        }
        return delegate.instantiate(arguments, dispatcher);
    }

    private boolean isEligibleMacro(InstantiatedFunction<T> instantiated) {
        if (!(delegate instanceof MacroFunction) || !(instantiated instanceof PlainTextFunction<?>)) {
            return false;
        }
        return delegate.id() == null || !ProbeConfiguration.isNamespaceExcluded(delegate.id().getNamespace());
    }

    @SuppressWarnings("unchecked")
    private InstantiatedFunction<T> specializeMacro(PlainTextFunction<?> plainTextFunction) {
        boolean shouldSpecialize = ProbeConfiguration.scoreAddPrototypeEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()
                || ProbeConfiguration.fusedRegionPrototypeEnabled()
                || ProbeConfiguration.bytecodeRegionPrototypeEnabled();
        if (!shouldSpecialize && !ProbeConfiguration.commandCallbackMetricsEnabled()) {
            return (InstantiatedFunction<T>) plainTextFunction;
        }
        InstantiatedFunction<T> cached = macroCompilationCache.get(plainTextFunction);
        if (cached != null) {
            return cached;
        }
        if (shouldSpecialize) {
            ScoreAddPrototype.compile(plainTextFunction, delegate.id());
        }
        if (ProbeConfiguration.commandCallbackMetricsEnabled()) {
            CommandCallbackMetricPrototype.compile(plainTextFunction);
        }
        InstantiatedFunction<T> result = (InstantiatedFunction<T>) plainTextFunction;
        PlainTextFunction<CommandSourceStack> typedFunction =
                (PlainTextFunction<CommandSourceStack>) plainTextFunction;
        if (ProbeConfiguration.bytecodeRegionPrototypeEnabled()
                && ProbeConfiguration.bytecodeMacroEnabled()) {
            result = (InstantiatedFunction<T>) BytecodeRegionPrototype.compile(typedFunction);
        } else if (ProbeConfiguration.fusedRegionForFunction(delegate.id())) {
            result = (InstantiatedFunction<T>) FusedRegionPrototype.compile(typedFunction);
        }
        macroCompilationCache.put(plainTextFunction, result);
        return result;
    }

    public boolean originalFallbackRetained(CommandDispatcher<T> dispatcher)
            throws FunctionInstantiationException {
        if (compiledInstantiation == null) {
            return delegate != null;
        }
        InstantiatedFunction<T> original = delegate.instantiate(null, dispatcher);
        if (compiledInstantiation == original) {
            return true;
        }
        return FusedRegionPrototype.retainsOriginal(
                (InstantiatedFunction<CommandSourceStack>) (Object) compiledInstantiation,
                (InstantiatedFunction<CommandSourceStack>) (Object) original
        );
    }
}
