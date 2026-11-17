package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerQueueCpuProbe;
import net.minecraft.commands.execution.CommandQueueEntry;
import net.minecraft.commands.execution.ExecutionContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Research-only separation of CPU spent inside dequeued queue entries from
 * the enclosing runCommandQueue driver. All entries are timed, not just
 * optimized leaves; this includes vanilla functions and game-world work.
 */
@Mixin(CommandQueueEntry.class)
abstract class CommandQueueEntryMixin<T> {
    @Inject(method = "execute", at = @At("HEAD"))
    private void functionCompiler$queueEntryCpuBegin(ExecutionContext<T> context, CallbackInfo ci) {
        SchedulerQueueCpuProbe.entryEnter();
    }

    @Inject(method = "execute", at = @At("RETURN"))
    private void functionCompiler$queueEntryCpuEnd(ExecutionContext<T> context, CallbackInfo ci) {
        SchedulerQueueCpuProbe.entryExit();
    }
}
