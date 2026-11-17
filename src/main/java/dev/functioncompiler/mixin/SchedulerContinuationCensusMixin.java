package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
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
    }
}
