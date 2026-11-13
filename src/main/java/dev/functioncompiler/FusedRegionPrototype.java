package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.ExecutionContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.TraceCallbacks;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;

import java.util.ArrayList;
import java.util.List;

/**
 * Disabled-by-default experiment that executes adjacent literal fake-holder
 * ScoreAdd entries in one scheduler entry while retaining the original
 * per-command debit, result callback, error handling, and trace callbacks.
 */
public final class FusedRegionPrototype {
    private FusedRegionPrototype() {
    }

    public static InstantiatedFunction<CommandSourceStack> compile(
            PlainTextFunction<CommandSourceStack> original
    ) {
        return compile(original, commands -> {
            ProbeMetrics.fusedRegionsCompiled(original.id(), 1);
            return new FusedScoreAddRegion(original.id(), commands);
        });
    }

    public static UnboundEntryAction<CommandSourceStack> createInterpretedRegion(
            List<FusedCommand> commands
    ) {
        return new FusedScoreAddRegion(null, commands);
    }

    static InstantiatedFunction<CommandSourceStack> compile(
            PlainTextFunction<CommandSourceStack> original,
            RegionFactory regionFactory
    ) {
        List<UnboundEntryAction<CommandSourceStack>> compiled = new ArrayList<>();
        List<FusedCommand> pending = new ArrayList<>();
        int regionCount = 0;

        for (UnboundEntryAction<CommandSourceStack> entry : original.entries()) {
            FusedCommand candidate = fusedCommand(entry);
            if (candidate != null) {
                pending.add(candidate);
                continue;
            }

            regionCount += appendPendingRegion(compiled, pending, regionFactory);
            compiled.add(entry);
        }
        regionCount += appendPendingRegion(compiled, pending, regionFactory);

        if (regionCount == 0) {
            return original;
        }
        return new CompiledInstantiatedFunction(original, List.copyOf(compiled));
    }

    private static int appendPendingRegion(
            List<UnboundEntryAction<CommandSourceStack>> compiled,
            List<FusedCommand> pending,
            RegionFactory regionFactory
    ) {
        if (pending.size() < 2) {
            compiled.addAll(pending.stream().map(FusedCommand::original).toList());
            pending.clear();
            return 0;
        }

        List<FusedCommand> region = List.copyOf(pending);
        try {
            compiled.add(regionFactory.compile(region));
            pending.clear();
            return 1;
        } catch (RuntimeException | LinkageError failure) {
            // A candidate backend failure must preserve every original queue
            // entry. The entries still contain the ordinary ScoreAdd wrapper,
            // which itself retains the original Brigadier command.
            compiled.addAll(region.stream().map(FusedCommand::original).toList());
            pending.clear();
            return 0;
        }
    }

    static FusedCommand fusedCommand(UnboundEntryAction<CommandSourceStack> entry) {
        if (!(entry instanceof BuildContexts.Unbound<?> buildContexts)) {
            return null;
        }

        ContextChain<CommandSourceStack> chain;
        String commandInput;
        try {
            @SuppressWarnings("unchecked")
            BuildContextsAccessor<CommandSourceStack> accessor =
                    (BuildContextsAccessor<CommandSourceStack>) (Object) buildContexts;
            chain = accessor.functionCompiler$getCommand();
            commandInput = accessor.functionCompiler$getCommandInput();
        } catch (ClassCastException exception) {
            return null;
        }
        if (chain.getStage() != ContextChain.Stage.EXECUTE) {
            return null;
        }

        CommandContext<CommandSourceStack> context = chain.getTopContext();
        if (!(context.getCommand() instanceof FusableCommand) || context.isForked()) {
            return null;
        }
        return new FusedCommand(entry, chain, commandInput);
    }

    /**
     * Executes one original parsed command and returns false only when vanilla's
     * command quota prevents this region from reaching the next entry.
     */
    static boolean executeCommand(
            FusedCommand command,
            CommandSourceStack source,
            ExecutionContext<CommandSourceStack> context,
            Frame frame
    ) {
        ExecutionContextAccessor<CommandSourceStack> accessor =
                (ExecutionContextAccessor<CommandSourceStack>) (Object) context;
        if (accessor.functionCompiler$getCommandQuota() <= 0) {
            return false;
        }

        TraceCallbacks tracer = context.tracer();
        if (tracer != null) {
            tracer.onCommand(frame.depth(), command.commandInput());
        }

        context.incrementCost();
        int result;
        try {
            result = ContextChain.runExecutable(
                    command.command().getTopContext(),
                    source,
                    ExecutionCommandSource.resultConsumer(),
                    false
            );
        } catch (CommandSyntaxException exception) {
            source.handleError(exception, false, tracer);
            return true;
        }

        if (tracer != null) {
            tracer.onReturn(frame.depth(), command.commandInput(), result);
        }
        return true;
    }

    @FunctionalInterface
    interface RegionFactory {
        UnboundEntryAction<CommandSourceStack> compile(List<FusedCommand> commands);
    }

    record FusedCommand(
            UnboundEntryAction<CommandSourceStack> original,
            ContextChain<CommandSourceStack> command,
            String commandInput
    ) {
    }

    private static final class FusedScoreAddRegion
            implements UnboundEntryAction<CommandSourceStack> {
        private final List<FusedCommand> commands;
        private final Identifier functionId;

        private FusedScoreAddRegion(Identifier functionId, List<FusedCommand> commands) {
            this.functionId = functionId;
            this.commands = commands;
        }

        @Override
        public void execute(
                CommandSourceStack source,
                ExecutionContext<CommandSourceStack> context,
                Frame frame
        ) {
            if (ProbeConfiguration.scoreAddMetricsEnabled()) {
                ProbeMetrics.fusedRegionExecuted(functionId);
            }
            for (FusedCommand command : commands) {
                if (!executeCommand(command, source, context, frame)) {
                    return;
                }
            }
        }
    }

    private static final class CompiledInstantiatedFunction
            implements InstantiatedFunction<CommandSourceStack> {
        private final PlainTextFunction<CommandSourceStack> original;
        private final List<UnboundEntryAction<CommandSourceStack>> entries;

        private CompiledInstantiatedFunction(
                PlainTextFunction<CommandSourceStack> original,
                List<UnboundEntryAction<CommandSourceStack>> entries
        ) {
            this.original = original;
            this.entries = entries;
        }

        @Override
        public Identifier id() {
            return original.id();
        }

        @Override
        public List<UnboundEntryAction<CommandSourceStack>> entries() {
            return entries;
        }

        public PlainTextFunction<CommandSourceStack> original() {
            return original;
        }
    }

    public static boolean retainsOriginal(
            InstantiatedFunction<CommandSourceStack> compiled,
            InstantiatedFunction<CommandSourceStack> original
    ) {
        return compiled instanceof CompiledInstantiatedFunction fused
                && fused.original() == original;
    }

    public static int traceEntryCount(
            InstantiatedFunction<?> compiled,
            int reportedEntryCount
    ) {
        if (compiled instanceof CompiledInstantiatedFunction fused) {
            return fused.original().entries().size();
        }
        return reportedEntryCount;
    }
}
