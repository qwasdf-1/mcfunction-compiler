package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerPathCensus;
import com.mojang.brigadier.ResultConsumer;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.SchedulerPhaseCpuProbe;
import org.spongepowered.asm.mixin.injection.Redirect;
import java.util.Collection;
import dev.functioncompiler.SchedulerTaskCpuProbe;
import net.minecraft.commands.execution.tasks.BuildContexts;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(BuildContexts.class)
abstract class SchedulerBuildContextsCensusMixin {
    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V", at = @At("HEAD"))
    private void functionCompiler$countBuildContexts(CallbackInfo ci) {
        SchedulerPathCensus.buildContexts();
        SchedulerTaskCpuProbe.enter(SchedulerTaskCpuProbe.Path.BUILD);
    }

    @Inject(method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V", at = @At("RETURN"))
    private void functionCompiler$timedcountBuildContextsReturn(CallbackInfo ci) {
        SchedulerTaskCpuProbe.exit(SchedulerTaskCpuProbe.Path.BUILD);
    }
    /**
     * Inspected Minecraft 26.3 BuildContexts.execute at bci 197:
     * ContextChain.runModifier, source and fork inputs retained exactly.
     */
    @Redirect(
            method = "execute(Lnet/minecraft/commands/ExecutionCommandSource;Ljava/util/List;Lnet/minecraft/commands/execution/ExecutionContext;Lnet/minecraft/commands/execution/Frame;Lnet/minecraft/commands/execution/ChainModifiers;)V",
            at = @At(
                    value = "INVOKE",
                    target = "Lcom/mojang/brigadier/context/ContextChain;runModifier(Lcom/mojang/brigadier/context/CommandContext;Ljava/lang/Object;Lcom/mojang/brigadier/ResultConsumer;Z)Ljava/util/Collection;"
            )
    )
    @SuppressWarnings({"rawtypes", "unchecked"})
    private Collection<?> functionCompiler$measureModifierPhase(
            CommandContext<?> command, Object source, ResultConsumer<?> consumer,
            boolean forked
    ) throws CommandSyntaxException {
        long start = SchedulerPhaseCpuProbe.begin(SchedulerPhaseCpuProbe.Phase.MODIFIER);
        try {
            return ContextChain.runModifier((CommandContext) command, source,
                    (ResultConsumer) consumer, forked);
        } finally {
            SchedulerPhaseCpuProbe.end(SchedulerPhaseCpuProbe.Phase.MODIFIER, start);
        }
    }
}
