package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import dev.functioncompiler.SchedulerTaskCpuProbe;
import net.minecraft.commands.execution.tasks.CallFunction;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(CallFunction.class)
abstract class SchedulerCallFunctionCensusMixin {
    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V", at = @At("HEAD"))
    private void functionCompiler$countCallFunction(CallbackInfo ci) {
        SchedulerPathCensus.callFunction();
        SchedulerTaskCpuProbe.enter(SchedulerTaskCpuProbe.Path.CALL);
    }

    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V", at = @At("RETURN"))
    private void functionCompiler$timedcountCallFunctionReturn(CallbackInfo ci) {
        SchedulerTaskCpuProbe.exit(SchedulerTaskCpuProbe.Path.CALL);
    }
}
