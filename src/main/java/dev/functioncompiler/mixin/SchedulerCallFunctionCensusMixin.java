package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import net.minecraft.commands.execution.tasks.CallFunction;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(CallFunction.class)
abstract class SchedulerCallFunctionCensusMixin {
    @Inject(method = "execute", at = @At("HEAD"))
    private void functionCompiler$countCallFunction(CallbackInfo ci) {
        SchedulerPathCensus.callFunction();
    }
}
