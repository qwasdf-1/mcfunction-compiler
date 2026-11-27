package dev.functioncompiler.mixin;

import dev.functioncompiler.IR048DispatchCensus;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.resources.Identifier;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Register exact native source-position entries before the event. No wrapping. */
@Mixin(targets = "net.minecraft.commands.functions.FunctionBuilder")
abstract class IR048FunctionBuilderFixtureMixin {
    @Inject(method = "build", at = @At("RETURN"))
    private void fc$ir048Register(Identifier id, CallbackInfoReturnable<CommandFunction<?>> ci) {
        IR048DispatchCensus.register(id, ci.getReturnValue());
    }
}
