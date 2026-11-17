package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import dev.functioncompiler.SchedulerTaskCpuProbe;
import net.minecraft.commands.execution.tasks.ContinuationTask;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ContinuationTask.class)
abstract class SchedulerContinuationCensusMixin {
    @Inject(method = "execute(Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V", at = @At("HEAD"))
    private void functionCompiler$countContinuation(CallbackInfo ci) {
        SchedulerPathCensus.continuation();
        SchedulerTaskCpuProbe.enter(SchedulerTaskCpuProbe.Path.CONTINUATION);
    }

    @Inject(method = "execute(Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V", at = @At("RETURN"))
    private void functionCompiler$timedcountContinuationReturn(CallbackInfo ci) {
        SchedulerTaskCpuProbe.exit(SchedulerTaskCpuProbe.Path.CONTINUATION);
    }
}
