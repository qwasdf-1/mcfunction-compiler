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

import java.util.List;

final class DataCopyCommand implements FusableCommand {
    private final Command<CommandSourceStack> vanillaCommand;
    private final Identifier targetStorageId;
    private final NbtPathArgument.NbtPath targetPath;
    private final Identifier sourceStorageId;
    private final NbtPathArgument.NbtPath sourcePath;
    private final Identifier functionId;

    DataCopyCommand(
            Command<CommandSourceStack> vanillaCommand,
            Identifier targetStorageId,
            NbtPathArgument.NbtPath targetPath,
            Identifier sourceStorageId,
            NbtPathArgument.NbtPath sourcePath,
            Identifier functionId
    ) {
        this.vanillaCommand = vanillaCommand;
        this.targetStorageId = targetStorageId;
        this.targetPath = targetPath;
        this.sourceStorageId = sourceStorageId;
        this.sourcePath = sourcePath;
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
        CompoundTag targetTag = storage.get(targetStorageId);
        CompoundTag sourceTag = storage.get(sourceStorageId);

        List<Tag> sourceElements;
        try {
            sourceElements = (sourcePath == null)
                    ? List.of(sourceTag.copy())
                    : sourcePath.get(sourceTag);
        } catch (CommandSyntaxException exception) {
            sourceElements = null;
        }

        if (sourceElements == null || sourceElements.isEmpty()) {
            return vanillaCommand.run(context);
        }

        int modified = 0;
        try {
            modified = targetPath.set(targetTag, sourceElements.get(0).copy());
        } catch (CommandSyntaxException ignored) {
        }

        if (modified == 0) {
            return vanillaCommand.run(context);
        }

        storage.set(targetStorageId, targetTag);
        source.sendSuccess(
                () -> Component.translatable(
                        "commands.data.storage.modified",
                        Component.translationArg(targetStorageId)
                ),
                true
        );

        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return modified;
    }
}
