package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerForkBreakdownProbe;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.tasks.ContinuationTask;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.List;

/**
 * IR-021 research observer. The original continuation is identified only if
 * constructed during schedule() from the exact armed restore command. The
 * native queue task remains wholly untouched; later execute() calls represent
 * actual deferred one-by-one per-entity staging work, not child execution.
 */
@Mixin(ContinuationTask.class)
abstract class CompilerForkContinuationMixin {
    @Unique private boolean functionCompiler$ir021Tracked;
    @Unique private long functionCompiler$ir021Started=-1L;

    @Inject(
            method = "schedule(Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Ljava/util/List;Lnet/minecraft/commands/execution/tasks/ContinuationTask$TaskProvider;)V",
            at = @At("HEAD")
    )
    private static void functionCompiler$ir021ScheduleHead(
            ExecutionContext<?> context, Frame frame, List<?> sources,
            ContinuationTask.TaskProvider<?, ?> provider, CallbackInfo ci
    ) {
        CompilerForkBreakdownProbe.scheduleStart(sources);
    }

    @Inject(
            method = "schedule(Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Ljava/util/List;Lnet/minecraft/commands/execution/tasks/ContinuationTask$TaskProvider;)V",
            at = @At("RETURN")
    )
    private static void functionCompiler$ir021ScheduleReturn(
            ExecutionContext<?> context, Frame frame, List<?> sources,
            ContinuationTask.TaskProvider<?, ?> provider, CallbackInfo ci
    ) {
        CompilerForkBreakdownProbe.scheduleEnd();
    }

    @Inject(
            method = "<init>(Lnet/minecraft/commands/execution/tasks/ContinuationTask$TaskProvider;Ljava/util/List;Lnet/minecraft/commands/execution/Frame;)V",
            at = @At("RETURN")
    )
    private void functionCompiler$ir021TagNativeContinuation(
            ContinuationTask.TaskProvider<?, ?> provider, List<?> arguments,
            Frame frame, CallbackInfo ci
    ) {
        functionCompiler$ir021Tracked =
                CompilerForkBreakdownProbe.continuationConstructedForTarget();
    }

    @Inject(
            method = "execute(Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V",
            at = @At("HEAD")
    )
    private void functionCompiler$ir021DeferredStepHead(
            ExecutionContext<?> context, Frame frame, CallbackInfo ci
    ) {
        functionCompiler$ir021Started =
                CompilerForkBreakdownProbe.continuationStepStart(functionCompiler$ir021Tracked);
    }

    @Inject(
            method = "execute(Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;)V",
            at = @At("RETURN")
    )
    private void functionCompiler$ir021DeferredStepReturn(
            ExecutionContext<?> context, Frame frame, CallbackInfo ci
    ) {
        CompilerForkBreakdownProbe.continuationStepEnd(
                functionCompiler$ir021Tracked,functionCompiler$ir021Started);
        functionCompiler$ir021Started=-1L;
    }
}
