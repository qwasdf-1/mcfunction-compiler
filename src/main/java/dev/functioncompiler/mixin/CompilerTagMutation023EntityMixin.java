package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerTagMutation023Probe;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Marker;
import net.minecraft.world.level.storage.ValueInput;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Exact mapped Entity tag/lifecycle methods, opt-in read-only return probes. */
@Mixin(Entity.class)
abstract class CompilerTagMutation023EntityMixin {
    @Inject(method = "addTag(Ljava/lang/String;)Z", at = @At("RETURN"))
    private void functionCompiler$023Add(String name, CallbackInfoReturnable<Boolean> cir) {
        CompilerTagMutation023Probe.tagReturn((Entity)(Object)this, name, true, cir.getReturnValueZ());
    }

    @Inject(method = "removeTag(Ljava/lang/String;)Z", at = @At("RETURN"))
    private void functionCompiler$023Remove(String name, CallbackInfoReturnable<Boolean> cir) {
        CompilerTagMutation023Probe.tagReturn((Entity)(Object)this, name, false, cir.getReturnValueZ());
    }

    @Inject(method = "load(Lnet/minecraft/world/level/storage/ValueInput;)V", at = @At("RETURN"))
    private void functionCompiler$023Load(ValueInput input, CallbackInfo ci) {
        CompilerTagMutation023Probe.loaded((Entity)(Object)this);
    }

    @Inject(
            method = "setRemoved(Lnet/minecraft/world/entity/Entity$RemovalReason;)V",
            at = @At("HEAD")
    )
    private void functionCompiler$023SetRemoved(Entity.RemovalReason reason, CallbackInfo ci) {
        CompilerTagMutation023Probe.removing((Entity)(Object)this, reason);
    }
}
