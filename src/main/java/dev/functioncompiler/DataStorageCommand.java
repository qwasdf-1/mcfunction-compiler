package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.storage.CommandStorage;

final class DataStorageCommand implements FusableCommand {
    private final Command<CommandSourceStack> vanillaCommand;
    private final Identifier storageId;
    private final NbtPathArgument.NbtPath path;
    private final Tag value;
    private final boolean isRemove;
    private final Identifier functionId;

    DataStorageCommand(
            Command<CommandSourceStack> vanillaCommand,
            Identifier storageId,
            NbtPathArgument.NbtPath path,
            Tag value,
            boolean isRemove,
            Identifier functionId
    ) {
        this.vanillaCommand = vanillaCommand;
        this.storageId = storageId;
        this.path = path;
        this.value = value;
        this.isRemove = isRemove;
        this.functionId = functionId;
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context) throws CommandSyntaxException {
        if (ProbeConfiguration.scoreAddTimingEnabled()) {
            long started = System.nanoTime();
            try {
                return runUntimed(context);
            } finally {
                ProbeMetrics.scoreAddTimed(functionId, System.nanoTime() - started);
            }
        }
        return runUntimed(context);
    }

    private int runUntimed(CommandContext<CommandSourceStack> context)
            throws CommandSyntaxException {
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()) {
            return vanillaCommand.run(context);
        }

        CommandSourceStack source = context.getSource();
        CommandStorage storage = source.getServer().getCommandStorage();
        CompoundTag tag = storage.get(storageId);

        int modified;
        try {
            modified = isRemove ? path.remove(tag) : path.set(tag, value.copy());
        } catch (CommandSyntaxException exception) {
            return vanillaCommand.run(context);
        }

        if (modified == 0) {
            return vanillaCommand.run(context);
        }

        storage.set(storageId, tag);
        source.sendSuccess(
                () -> Component.translatable(
                        "commands.data.storage.modified",
                        Component.translationArg(storageId)
                ),
                true
        );

        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return modified;
    }
}
