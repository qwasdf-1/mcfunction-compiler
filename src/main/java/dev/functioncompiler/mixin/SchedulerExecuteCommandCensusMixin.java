package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
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
}
