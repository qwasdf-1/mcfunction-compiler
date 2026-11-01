package dev.functioncompiler.mixin;

import net.minecraft.commands.arguments.NbtPathArgument;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.commands.FunctionCommand;
import net.minecraft.server.commands.data.DataAccessor;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;

@Mixin(FunctionCommand.class)
public interface FunctionCommandInvoker {
    @Invoker("getArgumentTag")
    static CompoundTag functionCompiler$getArgumentTag(
            NbtPathArgument.NbtPath path,
            DataAccessor dataAccessor
    ) throws CommandSyntaxException {
        throw new AssertionError();
    }
}
