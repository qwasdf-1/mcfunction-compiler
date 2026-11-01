package dev.functioncompiler.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.commands.data.DataAccessor;
import net.minecraft.world.entity.Mob;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Bellows 1.1.2 treats filtered {@code home_pos} mutations as handled without
 * updating the mob's home position. Route that path through vanilla's complete
 * {@link DataAccessor#setData(CompoundTag)} implementation instead.
 */
@Pseudo
@Mixin(targets = "net.smithed.bellows.utils.MixinShortcuts", remap = false)
abstract class BellowsHomePosAdapterMixin {
    @Inject(method = "setData", at = @At("HEAD"), cancellable = true, remap = false)
    private static void functionCompiler$restoreVanillaHomePosition(
            DataAccessor dataAccessor,
            NbtPathArgument.NbtPath path,
            CompoundTag updatedData,
            Operation<Void> original,
            CallbackInfo callback
    ) throws CommandSyntaxException {
        if (!(dataAccessor instanceof EntityDataAccessorAccessor accessor)
                || !(accessor.functionCompiler$getEntity() instanceof Mob)) {
            return;
        }

        if (!"home_pos".equals(topLevelPath(path.asString()))) {
            return;
        }

        CompoundTag fullData = dataAccessor.getData();
        fullData.merge(updatedData);
        if (!updatedData.contains("home_pos")) {
            fullData.remove("home_pos");
        }

        original.call(dataAccessor, fullData);
        callback.cancel();
    }

    private static String topLevelPath(String path) {
        int end = path.length();
        for (char delimiter : new char[]{'[', '.', '{'}) {
            int index = path.indexOf(delimiter);
            if (index >= 0) {
                end = Math.min(end, index);
            }
        }
        return path.substring(0, end);
    }
}
