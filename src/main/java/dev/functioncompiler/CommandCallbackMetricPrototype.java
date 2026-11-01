package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.CommandContextAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.CustomCommandExecutor;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.PlainTextFunction;

/** Opt-in wrappers that count ordinary Brigadier leaf callbacks in function queues. */
public final class CommandCallbackMetricPrototype {
    private CommandCallbackMetricPrototype() {
    }

    public static void compile(CommandFunction<?> function) {
        if (!(function instanceof PlainTextFunction<?> plainFunction)) {
            return;
        }

        for (UnboundEntryAction<?> entry : plainFunction.entries()) {
            if (entry instanceof BuildContexts.Unbound<?> buildContexts) {
                compileEntry(buildContexts);
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static void compileEntry(BuildContexts.Unbound<?> buildContexts) {
        ContextChain<CommandSourceStack> chain;
        try {
            chain = ((BuildContextsAccessor<CommandSourceStack>) (Object) buildContexts)
                    .functionCompiler$getCommand();
        } catch (ClassCastException exception) {
            return;
        }

        ContextChain<CommandSourceStack> executable = chain;
        while (executable.getStage() != ContextChain.Stage.EXECUTE) {
            executable = executable.nextStage();
            if (executable == null) {
                return;
            }
        }

        CommandContext<CommandSourceStack> context = executable.getTopContext();
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null
                || command instanceof CustomCommandExecutor<?>
                || command instanceof CallbackMetricCommand) {
            return;
        }

        CommandContextAccessor<CommandSourceStack> accessor =
                (CommandContextAccessor<CommandSourceStack>) (Object) context;
        accessor.functionCompiler$setCommand(new CallbackMetricCommand(
                command,
                ProbeConfiguration.scoreAddPrototypeEnabled()
                        && command instanceof ScoreAddCommand
        ));
    }

    private static final class CallbackMetricCommand implements Command<CommandSourceStack> {
        private final Command<CommandSourceStack> delegate;
        private final boolean optimizedScoreAdd;

        private CallbackMetricCommand(
                Command<CommandSourceStack> delegate,
                boolean optimizedScoreAdd
        ) {
            this.delegate = delegate;
            this.optimizedScoreAdd = optimizedScoreAdd;
        }

        @Override
        public int run(CommandContext<CommandSourceStack> context)
                throws CommandSyntaxException {
            if (ProbeMetrics.commandCallbackScopeActive()) {
                ProbeMetrics.commandCallbackExecuted(optimizedScoreAdd);
            }
            return delegate.run(context);
        }
    }
}
