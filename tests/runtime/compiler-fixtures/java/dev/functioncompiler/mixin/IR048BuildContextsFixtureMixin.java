package dev.functioncompiler.mixin;

import dev.functioncompiler.IR048DispatchCensus;
import net.minecraft.commands.execution.tasks.BuildContexts;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Fixture-only observer at the pinned native BuildContexts entry and custom terminal. */
@Mixin(BuildContexts.class)
abstract class IR048BuildContextsFixtureMixin {
    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V",
            at = @At("HEAD"))
    private void fc$ir048Start(CallbackInfo ci) {
        IR048DispatchCensus.buildStart(this);
    }

    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V",
            at = @At(value = "INVOKE", target = "Lnet/minecraft/commands/execution/CustomCommandExecutor;run(Ljava/lang/Object;Lcom/mojang/brigadier/context/ContextChain;Lnet/minecraft/commands/execution/ChainModifiers;Lnet/minecraft/commands/execution/ExecutionControl;)V"))
    private void fc$ir048Terminal(CallbackInfo ci) {
        IR048DispatchCensus.customTerminal();
    }

    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V",
            at = @At("RETURN"))
    private void fc$ir048End(CallbackInfo ci) {
        IR048DispatchCensus.buildEnd(this);
    }
}
