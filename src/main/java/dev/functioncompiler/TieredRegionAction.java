package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.ExecutionContext;
import net.minecraft.commands.execution.Frame;
import net.minecraft.commands.execution.UnboundEntryAction;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

final class TieredRegionAction implements UnboundEntryAction<CommandSourceStack> {
    private final List<FusedRegionPrototype.FusedCommand> commands;
    private final UnboundEntryAction<CommandSourceStack> interpretedRegion;
    private final int threshold;
    private final AtomicInteger invocations = new AtomicInteger();
    private volatile UnboundEntryAction<CommandSourceStack> bytecodeRegion;

    TieredRegionAction(List<FusedRegionPrototype.FusedCommand> commands, int threshold) {
        this.commands = commands;
        this.interpretedRegion = FusedRegionPrototype.createInterpretedRegion(commands);
        this.threshold = threshold;
    }

    @Override
    public void execute(
            CommandSourceStack source,
            ExecutionContext<CommandSourceStack> context,
            Frame frame
    ) {
        UnboundEntryAction<CommandSourceStack> jitted = bytecodeRegion;
        if (jitted != null) {
            jitted.execute(source, context, frame);
            return;
        }

        int count = invocations.incrementAndGet();
        if (count >= threshold && bytecodeRegion == null) {
            synchronized (this) {
                if (bytecodeRegion == null) {
                    bytecodeRegion = BytecodeRegionPrototype.compileRegionNow(commands);
                    ProbeMetrics.bytecodeTieredJitTriggered();
                }
            }
            bytecodeRegion.execute(source, context, frame);
            return;
        }

        interpretedRegion.execute(source, context, frame);
    }

    List<FusedRegionPrototype.FusedCommand> commands() {
        return commands;
    }
}
