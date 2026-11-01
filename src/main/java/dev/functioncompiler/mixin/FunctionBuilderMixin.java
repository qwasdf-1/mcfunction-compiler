package dev.functioncompiler.mixin;

import dev.functioncompiler.ProbeConfiguration;
import dev.functioncompiler.ProbeFunctionWrapper;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.MacroFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "net.minecraft.commands.functions.FunctionBuilder")
abstract class FunctionBuilderMixin {
    @Inject(method = "build", at = @At("RETURN"), cancellable = true)
    private void functionCompiler$wrapPlainFunction(
            Identifier id,
            CallbackInfoReturnable<CommandFunction<?>> callback
    ) {
        if (!ProbeConfiguration.wrapperEnabled()) {
            return;
        }

        CommandFunction<?> built = callback.getReturnValue();
        boolean compileMacroExpansion = built instanceof MacroFunction
                && (ProbeConfiguration.scoreAddPrototypeEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()
                || ProbeConfiguration.commandCallbackMetricsEnabled());
        if (built instanceof PlainTextFunction<?> || compileMacroExpansion) {
            callback.setReturnValue(wrap(built));
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static CommandFunction<?> wrap(CommandFunction<?> function) {
        return new ProbeFunctionWrapper(function);
    }
}
