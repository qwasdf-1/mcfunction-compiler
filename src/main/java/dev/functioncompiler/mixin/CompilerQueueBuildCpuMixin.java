package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerQueueCpuProbe;
import dev.functioncompiler.CompilerRestoreCpuProbe;
import dev.functioncompiler.CompilerForkBreakdownProbe;
import dev.functioncompiler.CompilerSelector022Probe;
import net.minecraft.commands.execution.tasks.BuildContexts;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * RESEARCH-ONLY: exact SHA-pinned enqueue_match predicate BuildContexts stage.
 * No mutation/cancellation; outside CPU005 the head returns without clocks.
 */
@Mixin(BuildContexts.class)
abstract class CompilerQueueBuildCpuMixin {
    @Shadow @Final private String commandInput;
    @Unique private long functionCompiler$cpu005Started = -1L;
    @Unique private long functionCompiler$cpu020Started = -1L;

    @Inject(
            method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V",
            at = @At("HEAD")
    )
    private void functionCompiler$cpu005BuildHead(CallbackInfo info) {
        functionCompiler$cpu005Started = CompilerQueueCpuProbe.beginBuild(commandInput);
        functionCompiler$cpu020Started = CompilerRestoreCpuProbe.beginBuild(commandInput);
        CompilerForkBreakdownProbe.buildStart(commandInput);
        CompilerSelector022Probe.buildStart(commandInput);
    }

    @Inject(
            method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V",
            at = @At("RETURN")
    )
    private void functionCompiler$cpu005BuildReturn(CallbackInfo info) {
        CompilerQueueCpuProbe.endBuild(commandInput, functionCompiler$cpu005Started);
        functionCompiler$cpu005Started = -1L;
        CompilerRestoreCpuProbe.endBuild(commandInput, functionCompiler$cpu020Started);
        functionCompiler$cpu020Started = -1L;
        CompilerForkBreakdownProbe.buildEnd(commandInput);
        CompilerSelector022Probe.buildEnd(commandInput);
    }
}
