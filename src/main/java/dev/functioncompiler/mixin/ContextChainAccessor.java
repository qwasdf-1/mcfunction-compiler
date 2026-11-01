package dev.functioncompiler.mixin;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

import java.util.List;

@Mixin(ContextChain.class)
public interface ContextChainAccessor<S> {
    @Accessor("modifiers")
    List<CommandContext<S>> functionCompiler$getModifiers();

    @Accessor("executable")
    CommandContext<S> functionCompiler$getExecutable();
}
