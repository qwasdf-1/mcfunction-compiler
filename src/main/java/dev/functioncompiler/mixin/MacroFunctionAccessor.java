package dev.functioncompiler.mixin;

import net.minecraft.commands.functions.MacroFunction;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

import java.util.List;

@Mixin(MacroFunction.class)
public interface MacroFunctionAccessor {
    @Accessor("parameters")
    List<String> functionCompiler$getParameters();
}
