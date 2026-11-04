package dev.functioncompiler.mixin;

import dev.functioncompiler.ProbeConfiguration;
import dev.functioncompiler.ProbeMetrics;
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
        // Count every function the datapack load produces, grouped by namespace,
        // so FunctionCoverageReport can report totals once per reload.
        if (id != null) {
            ProbeMetrics.functionLoaded(id.getNamespace());
        }

        if (!ProbeConfiguration.wrapperEnabled()) {
            return;
        }

        CommandFunction<?> built = callback.getReturnValue();
        boolean compileMacroExpansion = built instanceof MacroFunction
                && (ProbeConfiguration.scoreAddPrototypeEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()
                || ProbeConfiguration.commandCallbackMetricsEnabled());
        if (built instanceof PlainTextFunction<?> || compileMacroExpansion) {
            // "Covered" is counted where the specialization actually happens
            // (ProbeMetrics.scoreAddCompiled), not here: a wrapped function in an
            // excluded namespace is wrapped but not covered.
            callback.setReturnValue(wrap(built));
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static CommandFunction<?> wrap(CommandFunction<?> function) {
        return new ProbeFunctionWrapper(function);
    }
}
