package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import net.minecraft.commands.execution.CommandQueueEntry;
import net.minecraft.commands.execution.ExecutionContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Count actual dequeued entries independently of task-specific method hooks. */
@Mixin(CommandQueueEntry.class)
abstract class SchedulerPathQueueEntryMixin<T> {
    @Inject(method = "execute", at = @At("HEAD"))
    private void functionCompiler$countDequeued(ExecutionContext<T> context, CallbackInfo ci) {
        SchedulerPathCensus.queueEntry();
    }
}
