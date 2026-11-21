package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerForkBreakdownProbe;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.selector.EntitySelector;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;

/** IR-021 exact original source's native selector scan, read-only. */
@Mixin(EntitySelector.class)
abstract class CompilerForkEntitySelectorMixin {
    @Inject(
            method = "findEntities(Lnet/minecraft/commands/CommandSourceStack;)Ljava/util/List;",
            at = @At("HEAD")
    )
    private void functionCompiler$ir021EntitySelectionHead(
            CommandSourceStack source, CallbackInfoReturnable<List<? extends Entity>> ci
    ) {
        CompilerForkBreakdownProbe.selectorStart();
    }

    @Inject(
            method = "findEntities(Lnet/minecraft/commands/CommandSourceStack;)Ljava/util/List;",
            at = @At("RETURN")
    )
    private void functionCompiler$ir021EntitySelectionReturn(
            CommandSourceStack source, CallbackInfoReturnable<List<? extends Entity>> ci
    ) {
        CompilerForkBreakdownProbe.selectorEnd(ci.getReturnValue());
    }
}
