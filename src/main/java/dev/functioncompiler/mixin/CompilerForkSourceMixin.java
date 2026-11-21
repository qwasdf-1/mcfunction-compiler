package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerForkBreakdownProbe;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** IR-021 exact fork path's native per-entity source mapping. */
@Mixin(CommandSourceStack.class)
abstract class CompilerForkSourceMixin {
    @Inject(
            method = "withEntity(Lnet/minecraft/world/entity/Entity;)Lnet/minecraft/commands/CommandSourceStack;",
            at = @At("HEAD")
    )
    private void functionCompiler$ir021SourceHead(
            Entity entity, CallbackInfoReturnable<CommandSourceStack> ci
    ) {
        CompilerForkBreakdownProbe.entitySourceStart();
    }

    @Inject(
            method = "withEntity(Lnet/minecraft/world/entity/Entity;)Lnet/minecraft/commands/CommandSourceStack;",
            at = @At("RETURN")
    )
    private void functionCompiler$ir021SourceReturn(
            Entity entity, CallbackInfoReturnable<CommandSourceStack> ci
    ) {
        CompilerForkBreakdownProbe.entitySourceEnd();
    }
}
