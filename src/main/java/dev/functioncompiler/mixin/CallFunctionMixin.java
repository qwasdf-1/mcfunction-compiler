package dev.functioncompiler.mixin;

import dev.functioncompiler.FusedRegionPrototype;
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
                FusedRegionPrototype.traceEntryCount(function, compiledEntryCount)
        );
    }
}
