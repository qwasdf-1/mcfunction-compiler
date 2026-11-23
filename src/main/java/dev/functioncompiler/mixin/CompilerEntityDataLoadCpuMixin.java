package dev.functioncompiler.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import dev.functioncompiler.CompilerEntityWritebackProbe;
import net.minecraft.server.commands.data.EntityDataAccessor;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.storage.ValueInput;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * IR-031 exact removable-cost boundary: time only Entity.load called by the
 * native EntityDataAccessor.setData implementation while the outer callback
 * has established the exact unmounted Marker coordinate-store context.
 */
@Mixin(EntityDataAccessor.class)
abstract class CompilerEntityDataLoadCpuMixin {
    @WrapOperation(
            method = "setData(Lnet/minecraft/nbt/CompoundTag;)V",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/minecraft/world/entity/Entity;"
                            + "load(Lnet/minecraft/world/level/storage/ValueInput;)V"
            )
    )
    private void functionCompiler$ir031EntityLoad(
            Entity entity,
            ValueInput input,
            Operation<Void> original
    ) {
        long started = CompilerEntityWritebackProbe.beginEntityLoad(entity);
        try {
            original.call(entity, input);
        } finally {
            CompilerEntityWritebackProbe.endEntityLoad(started);
        }
    }
}
