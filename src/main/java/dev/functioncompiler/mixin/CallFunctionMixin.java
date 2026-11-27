package dev.functioncompiler.mixin;

import dev.functioncompiler.FusedRegionPrototype;
import dev.functioncompiler.DirectSchedulerPrototype;
import dev.functioncompiler.TypedScoreIRDirectScheduler;
import dev.functioncompiler.TypedScoreIR;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.TraceCallbacks;
import net.minecraft.commands.execution.tasks.CallFunction;
import net.minecraft.commands.functions.InstantiatedFunction;
import net.minecraft.resources.Identifier;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(CallFunction.class)
abstract class CallFunctionMixin<T extends ExecutionCommandSource<T>> {
    @Shadow @Final private InstantiatedFunction<T> function;
    @Shadow @Final private CommandResultCallback resultCallback;
    @Shadow @Final private boolean returnParentFrame;
    /**
     * Bypass the child function frame only in the proven straight-line island.
     * Any callback, trace, control-flow or unsupported command falls through
     * to CallFunction.execute and the original fused-region representation.
     */
    /**
     * IR-012: reuse the trusted CallFunction interception boundary, but run
     * a wholly typed compiled function via a resumable PC and queued ASM
     * chunks. All result/trace/return and unsupported cases remain vanilla.
     */
    @Inject(method = "execute", at = @At("HEAD"), cancellable = true)
    private void functionCompiler$typedDirectCallIfSafe(
            T source, ExecutionContext<T> context, Frame frame, CallbackInfo ci
    ) {
        if (TypedScoreIRDirectScheduler.tryExecute(
                function, source, context, frame, resultCallback, returnParentFrame)) {
            ci.cancel();
        }
    }

    @Inject(method = "execute", at = @At("HEAD"), cancellable = true)
    private void functionCompiler$directCallIfSafe(
            T source, ExecutionContext<T> context, Frame frame, CallbackInfo ci
    ) {
        if (DirectSchedulerPrototype.tryExecute(
                function, source, context, frame, resultCallback, returnParentFrame)) {
            ci.cancel();
        }
    }


    @Redirect(
            method = "execute",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/minecraft/commands/execution/TraceCallbacks;onCall(ILnet/minecraft/resources/Identifier;I)V"
            )
    )
    private void functionCompiler$preserveLogicalFunctionSize(
            TraceCallbacks tracer,
            int depth,
            Identifier functionId,
            int compiledEntryCount
    ) {
        tracer.onCall(
                depth,
                functionId,
                TypedScoreIR.originalTraceEntryCount(
                        function,
                        DirectSchedulerPrototype.traceEntryCount(
                                function,
                                FusedRegionPrototype.traceEntryCount(function, compiledEntryCount)))
        );
    }
}
