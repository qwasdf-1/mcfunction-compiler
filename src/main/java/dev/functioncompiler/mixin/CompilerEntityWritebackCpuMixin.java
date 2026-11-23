package dev.functioncompiler.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.llamalad7.mixinextras.sugar.Local;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.CompilerEntityWritebackProbe;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.commands.ExecuteCommand;
import net.minecraft.server.commands.data.DataAccessor;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * IR-031 measurement boundary only. Establishes an exact, synchronous context
 * around the original execute-store setter; the Operation is always called.
 */
@Mixin(ExecuteCommand.class)
abstract class CompilerEntityWritebackCpuMixin {
    @WrapOperation(
            method = "lambda$storeData$0(Lnet/minecraft/server/commands/data/DataAccessor;Z"
                    + "Lnet/minecraft/commands/arguments/NbtPathArgument$NbtPath;"
                    + "Ljava/util/function/IntFunction;ZI)V",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/minecraft/server/commands/data/DataAccessor;"
                            + "setData(Lnet/minecraft/nbt/CompoundTag;)V"
            )
    )
    private static void functionCompiler$ir031Writeback(
            DataAccessor accessor,
            CompoundTag compound,
            Operation<Void> original,
            @Local(argsOnly = true) NbtPathArgument.NbtPath path
    ) throws CommandSyntaxException {
        int axis = CompilerEntityWritebackProbe.beginStore(path, accessor);
        try {
            original.call(accessor, compound);
        } finally {
            CompilerEntityWritebackProbe.endStore(axis);
        }
    }
}
