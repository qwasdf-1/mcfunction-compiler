package dev.functioncompiler.mixin;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(CommandContext.class)
public interface CommandContextAccessor<S> {
    @Mutable
    @Accessor("command")
    void functionCompiler$setCommand(Command<S> command);
}
