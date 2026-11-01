package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.ExecutionContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.resources.Identifier;
import net.minecraft.world.entity.Entity;

import java.util.List;

final class InlinedForkingCommand implements FusableCommand {
    private final ContextChain<CommandSourceStack> fallbackChain;
    private final ForkModifierParser.CandidateResolver candidateResolver;
    private final ForkModifierParser.ForkTransformer forkTransformer;
    private final List<ContextModifierCommand.Transformation> downstreamTransformations;
    private final Command<CommandSourceStack> innerCommand;
    private final Identifier functionId;

    InlinedForkingCommand(
            ContextChain<CommandSourceStack> fallbackChain,
            ForkModifierParser.CandidateResolver candidateResolver,
            ForkModifierParser.ForkTransformer forkTransformer,
            List<ContextModifierCommand.Transformation> downstreamTransformations,
            Command<CommandSourceStack> innerCommand,
            Identifier functionId
    ) {
        this.fallbackChain = fallbackChain;
        this.candidateResolver = candidateResolver;
        this.forkTransformer = forkTransformer;
        this.downstreamTransformations = downstreamTransformations;
        this.innerCommand = innerCommand;
        this.functionId = functionId;
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context) throws CommandSyntaxException {
        if (ProbeConfiguration.scoreAddTimingEnabled()) {
            long started = System.nanoTime();
            try {
                return runUntimed(context);
            } finally {
                ProbeMetrics.scoreAddTimed(functionId, System.nanoTime() - started);
            }
        }
        return runUntimed(context);
    }

    private int runUntimed(CommandContext<CommandSourceStack> context)
            throws CommandSyntaxException {
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()) {
            return fallbackChain.executeAll(
                    context.getSource(),
                    ExecutionCommandSource.resultConsumer()
            );
        }

        CommandSourceStack source = context.getSource();
        List<? extends Entity> entities = candidateResolver.resolve(source);
        if (entities.isEmpty()) {
            return 0;
        }

        ExecutionContext<CommandSourceStack> execContext = ExecutionContextBridge.currentContext();
        if (execContext != null && entities.size() > execContext.forkLimit()) {
            throw BuildContexts.ERROR_FORK_LIMIT_REACHED.create(execContext.forkLimit());
        }

        int total = executeForEntities(context, entities, execContext);

        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return total;
    }

    private int executeForEntities(
            CommandContext<CommandSourceStack> context,
            List<? extends Entity> entities,
            ExecutionContext<CommandSourceStack> execContext
    ) throws CommandSyntaxException {
        int total = 0;
        CommandSourceStack baseSource = context.getSource();
        for (Entity entity : entities) {
            if (!canDebit(execContext)) {
                break;
            }
            CommandSourceStack entitySource = applyTransformations(
                    context, forkTransformer.transform(baseSource, entity)
            );
            if (entitySource != null) {
                total += innerCommand.run(context.copyFor(entitySource));
            }
        }
        return total;
    }

    private static boolean canDebit(ExecutionContext<CommandSourceStack> execContext) {
        if (execContext == null) {
            return true;
        }
        @SuppressWarnings("unchecked")
        ExecutionContextAccessor<CommandSourceStack> accessor =
                (ExecutionContextAccessor<CommandSourceStack>) (Object) execContext;
        if (accessor.functionCompiler$getCommandQuota() <= 0) {
            return false;
        }
        execContext.incrementCost();
        return true;
    }

    private CommandSourceStack applyTransformations(
            CommandContext<CommandSourceStack> context,
            CommandSourceStack source
    ) throws CommandSyntaxException {
        CommandSourceStack current = source;
        for (ContextModifierCommand.Transformation transformation : downstreamTransformations) {
            current = transformation.apply(context, current);
            if (current == null) {
                return null;
            }
        }
        return current;
    }
}
