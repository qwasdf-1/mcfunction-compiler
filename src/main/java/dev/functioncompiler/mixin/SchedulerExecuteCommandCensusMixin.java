package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import net.minecraft.commands.execution.tasks.ExecuteCommand;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ExecuteCommand.class)
abstract class SchedulerExecuteCommandCensusMixin {
    @Inject(method = "execute", at = @At("HEAD"))
    private void functionCompiler$countExecuteCommand(CallbackInfo ci) {
        SchedulerPathCensus.executeCommand();
    }
}
