package dev.functioncompiler.mixin;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.ProbeConfiguration;
import dev.functioncompiler.SelectiveMacroArgumentPrototype;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.commands.ArgProvider;
import net.minecraft.server.commands.FunctionCommand;
import net.minecraft.server.commands.data.DataAccessor;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "net.minecraft.server.commands.FunctionCommand$2")
abstract class SelectiveMacroArgumentsMixin {
    @Inject(method = "arguments", at = @At("HEAD"), cancellable = true)
    private void functionCompiler$selectMacroArguments(
            CommandContext<CommandSourceStack> context,
            CallbackInfoReturnable<CompoundTag> callback
    ) throws CommandSyntaxException {
        if (!ProbeConfiguration.selectiveMacroArgumentsEnabled()) {
            return;
        }

        NbtPathArgument.NbtPath path = NbtPathArgument.getPath(context, "path");
        ArgProvider<DataAccessor> provider = ((FunctionCommandMacroProviderAccessor) this)
                .functionCompiler$getProvider();
        DataAccessor accessor = provider.access(context);
        CompoundTag selective = SelectiveMacroArgumentPrototype.tryBuild(
                path, accessor, context);
        if (selective != null) {
            callback.setReturnValue(selective);
            return;
        }

        callback.setReturnValue(FunctionCommandInvoker.functionCompiler$getArgumentTag(
                path, accessor));
    }
}
