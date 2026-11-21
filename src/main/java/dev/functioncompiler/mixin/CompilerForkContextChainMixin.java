package dev.functioncompiler.mixin;

import com.mojang.brigadier.ResultConsumer;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import dev.functioncompiler.CompilerForkBreakdownProbe;
import dev.functioncompiler.CompilerSelector022Probe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.Collection;

/**
 * IR-021, RESEARCH ONLY: measure exact original Brigadier redirect modifier
 * calls when they are inside the explicitly armed Blastback BuildContexts.
 * Delegates untouched to ContextChain.runModifier, including fork failures.
 */
@Mixin(ContextChain.class)
abstract class CompilerForkContextChainMixin {
    @Inject(
            method = "runModifier(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)Ljava/util/Collection;",
            at = @At("HEAD")
    )
    private static void functionCompiler$ir021ModifierHead(
            CommandContext<?> context, Object source, ResultConsumer<?> callbacks,
            boolean forked, CallbackInfoReturnable<Collection<?>> ci
    ) {
        CompilerForkBreakdownProbe.modifierStart(context);
        CompilerSelector022Probe.modifierStart(context);
    }

    @Inject(
            method = "runModifier(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)Ljava/util/Collection;",
            at = @At("RETURN")
    )
    private static void functionCompiler$ir021ModifierReturn(
            CommandContext<?> context, Object source, ResultConsumer<?> callbacks,
            boolean forked, CallbackInfoReturnable<Collection<?>> ci
    ) {
        CompilerForkBreakdownProbe.modifierEnd(ci.getReturnValue());
        CompilerSelector022Probe.modifierEnd();
    }
}
