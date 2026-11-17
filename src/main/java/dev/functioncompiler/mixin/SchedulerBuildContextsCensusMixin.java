package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import net.minecraft.commands.execution.tasks.BuildContexts;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(BuildContexts.class)
abstract class SchedulerBuildContextsCensusMixin {
    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V", at = @At("HEAD"))
    private void functionCompiler$countBuildContexts(CallbackInfo ci) {
        SchedulerPathCensus.buildContexts();
    }
}
