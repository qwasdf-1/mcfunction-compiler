package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerQueueCpuProbe;
import net.minecraft.commands.execution.tasks.ExecuteCommand;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * RESEARCH-ONLY: original ExecuteCommand.execute includes real
 * Command.run, result consumer and required entity NBT mutation.
 */
@Mixin(ExecuteCommand.class)
abstract class CompilerQueueExecuteCpuMixin {
    @Shadow @Final private String commandInput;
    @Unique private long functionCompiler$cpu005Started = -1L;

    @Inject(
            method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V",
            at = @At("HEAD")
    )
    private void functionCompiler$cpu005ExecuteHead(CallbackInfo info) {
        functionCompiler$cpu005Started = CompilerQueueCpuProbe.beginExecute(commandInput);
    }

    @Inject(
            method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V",
            at = @At("RETURN")
    )
    private void functionCompiler$cpu005ExecuteReturn(CallbackInfo info) {
        CompilerQueueCpuProbe.endExecute(commandInput, functionCompiler$cpu005Started);
        functionCompiler$cpu005Started = -1L;
    }
}
