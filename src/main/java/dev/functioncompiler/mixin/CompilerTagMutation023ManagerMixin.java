package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerTagMutation023Probe;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.entity.EntityAccess;
import net.minecraft.world.level.entity.PersistentEntitySectionManager;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Observes original storage addition and visibility starts/ends, including
 * chunk reloading; never changes entity lookup, section visibility or order.
 */
@Mixin(PersistentEntitySectionManager.class)
abstract class CompilerTagMutation023ManagerMixin {
    @Inject(
            method = "addEntity(Lnet/minecraft/world/level/entity/EntityAccess;Z)Z",
            at = @At("RETURN")
    )
    private void functionCompiler$023AddEntity(
            EntityAccess entity, boolean fromDisk, CallbackInfoReturnable<Boolean> cir
    ) {
        if (entity instanceof Entity original)
            CompilerTagMutation023Probe.managerAdded(original, cir.getReturnValueZ());
    }

    @Inject(
            method = "startTracking(Lnet/minecraft/world/level/entity/EntityAccess;)V",
            at = @At("HEAD")
    )
    private void functionCompiler$023Track(EntityAccess entity, CallbackInfo ci) {
        if (entity instanceof Entity original)
            CompilerTagMutation023Probe.tracking(original, true);
    }

    @Inject(
            method = "stopTracking(Lnet/minecraft/world/level/entity/EntityAccess;)V",
            at = @At("HEAD")
    )
    private void functionCompiler$023Untrack(EntityAccess entity, CallbackInfo ci) {
        if (entity instanceof Entity original)
            CompilerTagMutation023Probe.tracking(original, false);
    }
}
