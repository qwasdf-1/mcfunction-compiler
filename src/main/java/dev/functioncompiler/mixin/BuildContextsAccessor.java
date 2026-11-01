package dev.functioncompiler.mixin;

import com.mojang.brigadier.context.ContextChain;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.execution.tasks.BuildContexts;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(BuildContexts.class)
public interface BuildContextsAccessor<T extends ExecutionCommandSource<T>> {
    @Accessor("command")
    ContextChain<T> functionCompiler$getCommand();

    @Mutable
    @Accessor("command")
    void functionCompiler$setCommand(ContextChain<T> command);

    @Accessor("commandInput")
    String functionCompiler$getCommandInput();
}
