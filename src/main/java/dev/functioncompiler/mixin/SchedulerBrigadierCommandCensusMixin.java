package dev.functioncompiler.mixin;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.SchedulerPhaseCpuProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/**
 * Minecraft 26.3's resolved Brigadier ContextChain.runExecutable invokes
 * Command.run(CommandContext) exactly once per successful executable action.
 *
 * <p>Preserves the original command callback and all failure behavior.
 * Only the already-selected ExecuteCommand 1/32 sample reads CPU clocks.
 */
@Mixin(value = ContextChain.class, remap = false)
abstract class SchedulerBrigadierCommandCensusMixin {
    @Redirect(
            method = "runExecutable(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)I",
            at = @At(
                    value = "INVOKE",
                    target = "Lcom/mojang/brigadier/Command;run(Lcom/mojang/brigadier/context/CommandContext;)I",
                    remap = false
            ),
            remap = false
    )
    @SuppressWarnings({"rawtypes", "unchecked"})
    private static int functionCompiler$measureCommandImplementation(
            Command<?> original, CommandContext<?> context
    ) throws CommandSyntaxException {
        long started = SchedulerPhaseCpuProbe.begin(SchedulerPhaseCpuProbe.Phase.COMMAND);
        try {
            return ((Command) original).run((CommandContext) context);
        } finally {
            SchedulerPhaseCpuProbe.end(SchedulerPhaseCpuProbe.Phase.COMMAND, started);
        }
    }
}
