package dev.functioncompiler;

import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.ExecutionContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ChainModifiers;
import net.minecraft.commands.execution.CommandQueueEntry;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.TraceCallbacks;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.execution.tasks.ContinuationTask;
import net.minecraft.commands.execution.tasks.ExecuteCommand;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.LongAdder;

/**
 * IR-025 compiler runtime for the JVM-generated native-selector fork action.
 *
 * WHAT IS COMPILED: native-selector invocation, source mapping, equality guard,
 * and native continuation scheduling, without Brigadier redirect/context-copy
 * invocation per selected entity.
 *
 * WHAT IS NOT COMPILED: entity selection itself (original live EntitySelector);
 * result-producing scoreboard terminal (original native ExecuteCommand);
 * child queue/continuation scheduling (original Minecraft ContinuationTask).
 *
 * No persistent Entity or ScoreAccess references, global membership index,
 * cross-command caching, per-tick poll, native class rewrite or selector
 * replacement. If a dynamic objective assumption fails, use the exact
 * original BuildContexts.Unbound *before* any stage quota or effects.
 */
final class CompilerForkExecutor025 {
    private static final boolean ENABLED = false; // IR025/028 not CPU-qualified
    private static final boolean DIAGNOSTICS = Boolean.parseBoolean(
            System.getenv("FC_TYPED_IR_DIAGNOSTICS"));

    // Low quota semantics are deliberately left entirely to vanilla until
    // a separate exact bytecode/deferred-task admission gate is completed.
    // The compiled path still pays both native modifier debits in full.
    private static final int MIN_FAST_QUOTA = 1024;

    private static final LongAdder COMPILED = new LongAdder();
    private static final LongAdder EXECUTED = new LongAdder();
    private static final LongAdder FALLBACK = new LongAdder();
    private static final LongAdder FORK_VISITS = new LongAdder();
    private static final LongAdder SELECTED = new LongAdder();
    private static final LongAdder MATCHED = new LongAdder();
    private static final LongAdder SCHEDULED = new LongAdder();
    private static final LongAdder FORK_LIMIT_ERRORS = new LongAdder();
    private static final LongAdder SELECTOR_ERRORS = new LongAdder();

    private CompilerForkExecutor025() {}

    static boolean enabled() { return ENABLED && CompilerForkPlan024.enabled(); }

    static UnboundEntryAction<CommandSourceStack> compile(
            CompilerForkPlan024.Plan plan,
            UnboundEntryAction<CommandSourceStack> original
    ) {
        if (!enabled()) return original;
        try {
            UnboundEntryAction<CommandSourceStack> generated =
                    CompilerForkBytecode025.emit(plan, original);
            if (DIAGNOSTICS) COMPILED.increment();
            return generated;
        } catch (RuntimeException | LinkageError error) {
            FunctionCompilerMod.LOGGER.warn(
                    "IR025 native fork JIT emission failed; original retained: {}",
                    error.toString());
            return original;
        }
    }

    static void run(
            CompilerForkPlan024.Plan plan,
            UnboundEntryAction<CommandSourceStack> original,
            CommandSourceStack source,
            ExecutionContext<CommandSourceStack> context,
            Frame frame
    ) {
        // Uninstrumented production mode remains disabled. Runtime fallbacks
        // execute the ORIGINAL full BuildContexts action and never share
        // partially evaluated compiled state with it.
        if (!ENABLED || ((ExecutionContextAccessor<CommandSourceStack>) (Object) context)
                .functionCompiler$getCommandQuota() < MIN_FAST_QUOTA) {
            fallback(original, source, context, frame);
            return;
        }

        Scoreboard board = source.getServer().getScoreboard();
        Objective entityObjective = board.getObjective(plan.entityScoreObjective());
        Objective referenceObjective = board.getObjective(plan.comparisonObjective());
        Objective mutationObjective = board.getObjective(plan.mutationObjective());

        // Re-resolve Objectives every invocation. Neither a compiled constant
        // Objective nor an indexed/cached ScoreAccess may survive remove/readd.
        // Native handles missing and readonly objective errors / callbacks.
        if (entityObjective == null || referenceObjective == null
                || mutationObjective == null
                || mutationObjective.getCriteria().isReadOnly()) {
            fallback(original, source, context, frame);
            return;
        }

        if (DIAGNOSTICS) EXECUTED.increment();
        TraceCallbacks tracer = context.tracer();
        if (tracer != null) tracer.onCommand(frame.depth(), plan.commandInput());
        context.profiler().push(() -> plan.commandInput());
        try {
            // Exact 26.3 BuildContexts order: native initial as modifier quota
            // debit, native selector, all withEntity mappings, fork limit;
            // then one score-condition-stage debit even with zero candidates.
            context.incrementCost();
            List<? extends Entity> entities;
            try {
                entities = plan.nativeSelector().findEntities(source);
            } catch (CommandSyntaxException failure) {
                if (DIAGNOSTICS) SELECTOR_ERRORS.increment();
                source.handleError(failure, true, tracer);
                return;
            }
            if (DIAGNOSTICS) {
                FORK_VISITS.increment();
                SELECTED.add(entities.size());
            }

            List<CommandSourceStack> candidates = new ArrayList<>(entities.size());
            for (Entity entity : entities) {
                candidates.add(source.withEntity(entity));
            }
            if (candidates.size() >= context.forkLimit()) {
                if (DIAGNOSTICS) FORK_LIMIT_ERRORS.increment();
                source.handleError(
                        BuildContexts.ERROR_FORK_LIMIT_REACHED.create(context.forkLimit()),
                        true, tracer);
                return;
            }

            context.incrementCost();
            if (candidates.isEmpty()) return;

            ScoreHolder comparisonHolder = ScoreHolder.forNameOnly(plan.comparisonHolder());
            ReadOnlyScoreInfo comparisonInfo =
                    board.getPlayerScoreInfo(comparisonHolder, referenceObjective);
            if (comparisonInfo == null) return;
            int required = comparisonInfo.value();

            List<CommandSourceStack> passing = new ArrayList<>();
            for (CommandSourceStack entitySource : candidates) {
                // @s is the ACTUAL selected source for this invocation, not
                // the source from compilation or from the previous entity.
                Entity entity = entitySource.getEntity();
                ReadOnlyScoreInfo entityInfo =
                        entity == null ? null : board.getPlayerScoreInfo(entity, entityObjective);
                if (entityInfo != null && entityInfo.value() == required) {
                    passing.add(entitySource);
                }
            }
            if (passing.isEmpty()) return;

            if (DIAGNOSTICS) {
                MATCHED.add(passing.size());
                SCHEDULED.increment();
            }

            // Original native terminal command (including result feedback,
            // callback, errors and onReturn trace) and original Continuation-
            // Task policy (special cases 0/1/2, deferred steps for >2).
            ExecuteCommand<CommandSourceStack> originalTerminal =
                    new ExecuteCommand<>(plan.commandInput(),
                            ChainModifiers.DEFAULT.setForked(), plan.terminalContext());
            ContinuationTask.schedule(context, frame, passing,
                    (commandFrame, entitySource) -> new CommandQueueEntry<>(
                            commandFrame, originalTerminal.bind(entitySource)));
        } finally {
            context.profiler().pop();
        }
    }

    private static void fallback(
            UnboundEntryAction<CommandSourceStack> original,
            CommandSourceStack source,
            ExecutionContext<CommandSourceStack> context,
            Frame frame
    ) {
        if (DIAGNOSTICS) FALLBACK.increment();
        original.execute(source, context, frame);
    }

    static String diagnostics() {
        return "IR025 enabled=" + enabled()
                + " compiled_forks=" + COMPILED.sum()
                + " executed_forks=" + EXECUTED.sum()
                + " native_fallbacks=" + FALLBACK.sum()
                + " selector_scans=" + FORK_VISITS.sum()
                + " selected_sources=" + SELECTED.sum()
                + " passing_sources=" + MATCHED.sum()
                + " continuation_schedules=" + SCHEDULED.sum()
                + " fork_limit_errors=" + FORK_LIMIT_ERRORS.sum()
                + " selector_errors=" + SELECTOR_ERRORS.sum();
    }

    static int report(CommandSourceStack source) {
        source.sendSuccess(() -> Component.literal(diagnostics()), false);
        return 1;
    }
}
