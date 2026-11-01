package dev.functioncompiler.mixin;

import dev.functioncompiler.ProbeConfiguration;
import dev.functioncompiler.ProbeMetrics;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.execution.ChainModifiers;
import net.minecraft.commands.execution.ExecutionControl;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.FunctionCommand;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.Collection;

@Mixin(FunctionCommand.class)
abstract class FunctionCommandMixin {
    private static final Identifier FUNCTION_TIMING_TARGET = Identifier.fromNamespaceAndPath(
            "function_compiler_perf", "scoreboard");

    @Inject(method = "queueFunctions", at = @At("HEAD"))
    private static void functionCompiler$beginFunctionTiming(
            Collection<?> functions,
            CompoundTag arguments,
            ExecutionCommandSource<?> source,
            ExecutionCommandSource<?> originalSource,
            ExecutionControl<?> control,
            FunctionCommand.Callbacks<?> callbacks,
            ChainModifiers modifiers,
            CallbackInfo callback
    ) {
        if (!ProbeConfiguration.functionTimingEnabled()) {
            return;
        }
        boolean target = functions.stream()
                .filter(CommandFunction.class::isInstance)
                .map(CommandFunction.class::cast)
                .anyMatch(function -> FUNCTION_TIMING_TARGET.equals(function.id()));
        if (target) {
            ProbeMetrics.beginExecutionQueueTiming();
        }
    }
}
