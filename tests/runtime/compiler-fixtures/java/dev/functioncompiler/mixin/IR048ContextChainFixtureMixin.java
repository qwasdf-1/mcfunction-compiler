package dev.functioncompiler.mixin;

import com.mojang.brigadier.ResultConsumer;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import dev.functioncompiler.IR048DispatchCensus;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.Collection;

/** Count actual native modifier input and output cardinality; never replace a selector. */
@Mixin(ContextChain.class)
abstract class IR048ContextChainFixtureMixin {
    @Inject(method = "runModifier(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)Ljava/util/Collection;",
            at = @At("HEAD"))
    private static void fc$ir048ModifierStart(CommandContext<?> context, Object source,
            ResultConsumer<?> callbacks, boolean forked, CallbackInfoReturnable<Collection<?>> ci) {
        IR048DispatchCensus.modifierStart(context, forked);
    }

    @Inject(method = "runModifier(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)Ljava/util/Collection;",
            at = @At("RETURN"))
    private static void fc$ir048ModifierReturn(CommandContext<?> context, Object source,
            ResultConsumer<?> callbacks, boolean forked, CallbackInfoReturnable<Collection<?>> ci) {
        IR048DispatchCensus.modifierReturn(context, ci.getReturnValue());
    }
}
