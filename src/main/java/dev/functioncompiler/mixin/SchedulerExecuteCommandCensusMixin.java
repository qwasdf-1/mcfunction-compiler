package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import com.mojang.brigadier.ResultConsumer;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.SchedulerPhaseCpuProbe;
import org.spongepowered.asm.mixin.injection.Redirect;
import dev.functioncompiler.SchedulerTaskCpuProbe;
import net.minecraft.commands.execution.tasks.ExecuteCommand;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ExecuteCommand.class)
abstract class SchedulerExecuteCommandCensusMixin {
    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V", at = @At("HEAD"))
    private void functionCompiler$countExecuteCommand(CallbackInfo ci) {
        SchedulerPathCensus.executeCommand();
        SchedulerTaskCpuProbe.enter(SchedulerTaskCpuProbe.Path.EXECUTE);
    }

    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V", at = @At("RETURN"))
    private void functionCompiler$timedcountExecuteCommandReturn(CallbackInfo ci) {
        SchedulerTaskCpuProbe.exit(SchedulerTaskCpuProbe.Path.EXECUTE);
    }
    /**
     * Inspected Minecraft 26.3 ExecuteCommand.execute at bci 34:
     * ContextChain.runExecutable includes command run and result callback.
     */
    @Redirect(
            method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V",
            at = @At(
                    value = "INVOKE",
                    target = "Lcom/mojang/brigadier/context/ContextChain;runExecutable(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)I"
            )
    )
    @SuppressWarnings({"rawtypes", "unchecked"})
    private int functionCompiler$measureExecutablePhase(
            CommandContext<?> command, Object source, ResultConsumer<?> consumer,
            boolean forked
    ) throws CommandSyntaxException {
        long start = SchedulerPhaseCpuProbe.begin(SchedulerPhaseCpuProbe.Phase.EXECUTABLE);
        try {
            return ContextChain.runExecutable((CommandContext) command, source,
                    (ResultConsumer) consumer, forked);
        } finally {
            SchedulerPhaseCpuProbe.end(SchedulerPhaseCpuProbe.Phase.EXECUTABLE, start);
        }
    }
}
