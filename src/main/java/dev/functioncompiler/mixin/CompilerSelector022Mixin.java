package dev.functioncompiler.mixin;

import dev.functioncompiler.CompilerSelector022Probe;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.selector.EntitySelector;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.flag.FeatureFlagSet;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;
import java.util.function.Predicate;

/**
 * IR-022 bounded diagnostic: selects only exact original Blastback command
 * while FC_CPU022 explicit test window is active. Every native selector,
 * world lookup, predicate test and final result remains delegated unchanged.
 * Only test modes PLAIN/EMPTY/TIMED proxy type/predicate arguments; CONTROL
 * passes the original native objects through without identity replacement.
 */
@Mixin(EntitySelector.class)
abstract class CompilerSelector022Mixin {
    private static final String ADD =
            "addEntities(Ljava/util/List;Lnet/minecraft/server/level/ServerLevel;"
                    + "Lnet/minecraft/world/phys/AABB;Ljava/util/function/Predicate;)V";
    private static final String BOXED_GET =
            "Lnet/minecraft/server/level/ServerLevel;getEntities("
                    + "Lnet/minecraft/world/level/entity/EntityTypeTest;"
                    + "Lnet/minecraft/world/phys/AABB;Ljava/util/function/Predicate;"
                    + "Ljava/util/List;I)V";
    private static final String UNBOXED_GET =
            "Lnet/minecraft/server/level/ServerLevel;getEntities("
                    + "Lnet/minecraft/world/level/entity/EntityTypeTest;"
                    + "Ljava/util/function/Predicate;Ljava/util/List;I)V";

    @Inject(
            method = "findEntities(Lnet/minecraft/commands/CommandSourceStack;)Ljava/util/List;",
            at = @At("HEAD")
    )
    private void functionCompiler$ir022FindStart(
            CommandSourceStack source, CallbackInfoReturnable<List<?>> ci
    ) { CompilerSelector022Probe.findStart(); }

    @Inject(
            method = "findEntities(Lnet/minecraft/commands/CommandSourceStack;)Ljava/util/List;",
            at = @At("RETURN")
    )
    private void functionCompiler$ir022FindReturn(
            CommandSourceStack source, CallbackInfoReturnable<List<?>> ci
    ) { CompilerSelector022Probe.findEnd(ci.getReturnValue().size()); }

    @Inject(
            method = "getPredicate(Lnet/minecraft/world/phys/Vec3;"
                    + "Lnet/minecraft/world/phys/AABB;"
                    + "Lnet/minecraft/world/flag/FeatureFlagSet;)Ljava/util/function/Predicate;",
            at = @At("HEAD")
    )
    private void functionCompiler$ir022PredicateConstructStart(
            Vec3 pos, AABB box, FeatureFlagSet flags,
            CallbackInfoReturnable<Predicate<Entity>> ci
    ) { CompilerSelector022Probe.predicateBuildStart(); }

    @Inject(
            method = "getPredicate(Lnet/minecraft/world/phys/Vec3;"
                    + "Lnet/minecraft/world/phys/AABB;"
                    + "Lnet/minecraft/world/flag/FeatureFlagSet;)Ljava/util/function/Predicate;",
            at = @At("RETURN")
    )
    private void functionCompiler$ir022PredicateConstructReturn(
            Vec3 pos, AABB box, FeatureFlagSet flags,
            CallbackInfoReturnable<Predicate<Entity>> ci
    ) { CompilerSelector022Probe.predicateBuildEnd(); }

    @Inject(method = ADD, at = @At("HEAD"))
    private void functionCompiler$ir022GatherStart(
            List<Entity> result, ServerLevel level, AABB box, Predicate<Entity> predicate,
            CallbackInfo ci
    ) { CompilerSelector022Probe.gatherStart(result.size()); }

    @Inject(method = ADD, at = @At("RETURN"))
    private void functionCompiler$ir022GatherReturn(
            List<Entity> result, ServerLevel level, AABB box, Predicate<Entity> predicate,
            CallbackInfo ci
    ) { CompilerSelector022Probe.gatherEnd(result.size()); }

    @Inject(
            method = "sortAndLimit(Lnet/minecraft/world/phys/Vec3;Ljava/util/List;)Ljava/util/List;",
            at = @At("HEAD")
    )
    private void functionCompiler$ir022SortStart(
            Vec3 position,List<? extends Entity> entities,CallbackInfoReturnable<List<?>> ci
    ) { CompilerSelector022Probe.sortStart(entities.size()); }

    @Inject(
            method = "sortAndLimit(Lnet/minecraft/world/phys/Vec3;Ljava/util/List;)Ljava/util/List;",
            at = @At("RETURN")
    )
    private void functionCompiler$ir022SortReturn(
            Vec3 position,List<? extends Entity> entities,CallbackInfoReturnable<List<?>> ci
    ) { CompilerSelector022Probe.sortEnd(ci.getReturnValue().size()); }

    @SuppressWarnings({"rawtypes","unchecked"})
    @ModifyArg(method = ADD, at = @At(value = "INVOKE", target = BOXED_GET), index = 0)
    private EntityTypeTest functionCompiler$ir022TypeBoxed(EntityTypeTest original) {
        return CompilerSelector022Probe.typeArgument(original);
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    @ModifyArg(method = ADD, at = @At(value = "INVOKE", target = UNBOXED_GET), index = 0)
    private EntityTypeTest functionCompiler$ir022TypeUnboxed(EntityTypeTest original) {
        return CompilerSelector022Probe.typeArgument(original);
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    @ModifyArg(method = ADD, at = @At(value = "INVOKE", target = BOXED_GET), index = 2)
    private Predicate functionCompiler$ir022PredicateBoxed(Predicate original) {
        return CompilerSelector022Probe.predicateArgument(original);
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    @ModifyArg(method = ADD, at = @At(value = "INVOKE", target = UNBOXED_GET), index = 1)
    private Predicate functionCompiler$ir022PredicateUnboxed(Predicate original) {
        return CompilerSelector022Probe.predicateArgument(original);
    }
}
