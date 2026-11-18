package dev.functioncompiler.mixin;

import com.mojang.brigadier.ResultConsumer;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import dev.functioncompiler.SchedulerPhaseCpuProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/**
 * Research-only exact Brigadier 26.3 runExecutable callsite wrappers.
 *
 * Original bytecode: copyFor at bci 2, then Command.run at bci 13,
 * then onCommandComplete at bci 26 (success) or 49 (syntax failure).
 * The two callback INVOKEs share the exact signature and MUST both match.
 * All operations invoke the original method exactly once; CPU clock
 * interval closes in finally, even when the original method throws.
 */
@Mixin(value = ContextChain.class, remap = false)
abstract class SchedulerBrigadierPlumbingMixin {

    @Redirect(
            method = "runExecutable(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)I",
            at = @At(
                    value = "INVOKE",
                    target = "Lcom/mojang/brigadier/context/CommandContext;copyFor(Ljava/lang/Object;)Lcom/mojang/brigadier/context/CommandContext;",
                    remap = false
            ),
            require = 1,
            remap = false
    )
    @SuppressWarnings({"rawtypes", "unchecked"})
    private static CommandContext<?> functionCompiler$timedCopyFor(
            CommandContext<?> original, Object source
    ) {
        long token = SchedulerPhaseCpuProbe.begin(SchedulerPhaseCpuProbe.Phase.COPY);
        try {
            CommandContext<?> copied = ((CommandContext) original).copyFor(source);
            SchedulerPhaseCpuProbe.observedCopy(token, copied == original);
            return copied;
        } finally {
            SchedulerPhaseCpuProbe.end(SchedulerPhaseCpuProbe.Phase.COPY, token);
        }
    }

    @Redirect(
            method = "runExecutable(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)I",
            at = @At(
                    value = "INVOKE",
                    target = "Lcom/mojang/brigadier/ResultConsumer;onCommandComplete(Lcom/mojang/brigadier/context/CommandContext;ZI)V",
                    remap = false
            ),
            require = 2,
            remap = false
    )
    @SuppressWarnings({"rawtypes", "unchecked"})
    private static void functionCompiler$timedResultConsumer(
            ResultConsumer<?> original, CommandContext<?> command,
            boolean success, int result
    ) {
        long token = SchedulerPhaseCpuProbe.begin(SchedulerPhaseCpuProbe.Phase.RESULT);
        SchedulerPhaseCpuProbe.observedResult(token, success);
        try {
            ((ResultConsumer) original).onCommandComplete((CommandContext) command,
                    success, result);
        } finally {
            SchedulerPhaseCpuProbe.end(SchedulerPhaseCpuProbe.Phase.RESULT, token);
        }
    }
}
