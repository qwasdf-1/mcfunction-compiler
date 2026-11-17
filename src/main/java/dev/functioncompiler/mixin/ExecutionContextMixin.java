package dev.functioncompiler.mixin;

import dev.functioncompiler.ExecutionContextBridge;
import dev.functioncompiler.FunctionCompilerMod;
import dev.functioncompiler.ProbeConfiguration;
import dev.functioncompiler.ProbeMetrics;
import dev.functioncompiler.ProbeRuntimeTrace;
import dev.functioncompiler.SchedulerQueueCpuProbe;
import net.minecraft.commands.execution.CommandQueueEntry;
import net.minecraft.commands.execution.ExecutionContext;
import org.objectweb.asm.Opcodes;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.Deque;

@Mixin(ExecutionContext.class)
abstract class ExecutionContextMixin<T> {
    @Unique private int functionCompiler$commandCallbackMetricsScopeDepth;

    @Shadow @Final private Deque<CommandQueueEntry<T>> commandQueue;
    @Shadow private int commandQuota;

    @Inject(
            method = "runCommandQueue",
            at = @At(
                    value = "FIELD",
                    target = "Lnet/minecraft/commands/execution/ExecutionContext;commandQuota:I",
                    opcode = Opcodes.GETFIELD,
                    ordinal = 0
            )
    )
    private void functionCompiler$traceQueueBoundary(CallbackInfo callback) {
        if (ProbeConfiguration.schedulerArchitectureCountersEnabled()
                && !commandQueue.isEmpty()) {
            ProbeMetrics.archQueueBoundaryVisit();
        }
        if (ProbeRuntimeTrace.enabled()) {
            Object next = commandQueue.peekFirst();
            FunctionCompilerMod.LOGGER.info(
                    "FC_TRACE label={} event=queue-boundary quota={} next={}",
                    ProbeRuntimeTrace.label(), commandQuota,
                    next == null ? "empty" : next.getClass().getSimpleName());
        }
    }

    // Opt-in CPU accounting; the ordinary mode compiles to a static false gate.
    @Inject(method = "runCommandQueue", at = @At("HEAD"))
    private void functionCompiler$queueCpuBegin(CallbackInfo callback) {
        SchedulerQueueCpuProbe.queueEnter();
    }

    @Inject(method = "runCommandQueue", at = @At("RETURN"))
    private void functionCompiler$queueCpuEnd(CallbackInfo callback) {
        SchedulerQueueCpuProbe.queueExit();
    }

    @Inject(method = "runCommandQueue", at = @At("HEAD"))
    private void functionCompiler$beginCommandCallbackMetrics(CallbackInfo callback) {
        ExecutionContextBridge.push((ExecutionContext<?>) (Object) this);
        if (ProbeConfiguration.commandCallbackMetricsEnabled()
                && ProbeConfiguration.commandCallbackMetricsAllQueues()) {
            ProbeMetrics.beginCommandCallbackScope();
            functionCompiler$commandCallbackMetricsScopeDepth++;
        }
    }

    @Inject(method = "incrementCost", at = @At("TAIL"))
    private void functionCompiler$traceCostDebit(CallbackInfo callback) {
        if (ProbeConfiguration.schedulerArchitectureCountersEnabled()) {
            ProbeMetrics.archQuotaDebit();
        }
        if (ProbeRuntimeTrace.enabled()) {
            FunctionCompilerMod.LOGGER.info(
                    "FC_TRACE label={} event=cost-debit quota={}",
                    ProbeRuntimeTrace.label(), commandQuota);
        }
    }

    @Inject(method = "runCommandQueue", at = @At("RETURN"))
    private void functionCompiler$finishTrace(CallbackInfo callback) {
        ExecutionContextBridge.pop();
        if (functionCompiler$commandCallbackMetricsScopeDepth > 0) {
            functionCompiler$commandCallbackMetricsScopeDepth--;
            ProbeMetrics.endCommandCallbackScope();
        }
        if (ProbeConfiguration.commandCallbackMetricsEnabled()
                && ProbeMetrics.consumeCommandCallbackScopeEndRequest()) {
            ProbeMetrics.endCommandCallbackScope();
        }
        ProbeMetrics.endExecutionQueueTiming();
        if (ProbeRuntimeTrace.enabled()) {
            String event = commandQueue.isEmpty() ? "queue-complete" : "queue-yield";
            FunctionCompilerMod.LOGGER.info(
                    "FC_TRACE label={} event={} quota={} pending={}",
                    ProbeRuntimeTrace.label(), event, commandQuota,
                    commandQueue.isEmpty() ? "none" : commandQueue.peekFirst().getClass().getSimpleName());
            ProbeRuntimeTrace.end();
        }
    }
}
