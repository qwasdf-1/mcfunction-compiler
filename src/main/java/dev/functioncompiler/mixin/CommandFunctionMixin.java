package dev.functioncompiler.mixin;

import dev.functioncompiler.ProbeMetrics;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.resources.Identifier;
import com.mojang.brigadier.CommandDispatcher;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;

@Mixin(CommandFunction.class)
interface CommandFunctionMixin {
    @Inject(method = "fromLines", at = @At("RETURN"))
    private static void functionCompiler$recordProbeFunctionParse(
            Identifier id,
            CommandDispatcher<?> dispatcher,
            ExecutionCommandSource<?> source,
            List<String> lines,
            CallbackInfoReturnable<CommandFunction<?>> callback
    ) {
        if (id.toString().equals("function_compiler_probe:quota_three")) {
            ProbeMetrics.probeFunctionParsed();
        }
    }
}
