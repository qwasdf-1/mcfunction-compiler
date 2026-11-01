package dev.functioncompiler.mixin;

import net.minecraft.server.commands.ArgProvider;
import net.minecraft.server.commands.data.DataAccessor;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(targets = "net.minecraft.server.commands.FunctionCommand$2")
public interface FunctionCommandMacroProviderAccessor {
    @Accessor("val$provider")
    ArgProvider<DataAccessor> functionCompiler$getProvider();
}
