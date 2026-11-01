package dev.functioncompiler.mixin;

import net.minecraft.commands.execution.ExecutionContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(ExecutionContext.class)
public interface ExecutionContextAccessor<T> {
    @Accessor("commandQuota")
    int functionCompiler$getCommandQuota();
}
