package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.data.DataCommands;

import java.util.List;

final class DataStorageParser {
    private DataStorageParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier functionId) {
        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (names.size() < 5 || !"data".equals(names.get(0))) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || !command.getClass().isSynthetic()
                || command.getClass().getNestHost() != DataCommands.class) {
            return false;
        }

        String action = names.get(1);
        if ("remove".equals(action)) {
            return compileRemove(context, names, command, functionId);
        }
        if ("modify".equals(action)) {
            return compileModify(context, names, command, functionId);
        }
        return false;
    }

    private static boolean compileRemove(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            Command<CommandSourceStack> command,
            Identifier functionId
    ) {
        if (names.size() != 5
                || !"storage".equals(names.get(2))
                || !"target".equals(names.get(3))
                || !"path".equals(names.get(4))) {
            return false;
        }
        try {
            Identifier target = context.getArgument("target", Identifier.class);
            NbtPathArgument.NbtPath path = context.getArgument("path", NbtPathArgument.NbtPath.class);
            ScoreAddPrototype.applyCommand(
                    context,
                    new DataStorageCommand(command, target, path, null, true, functionId),
                    functionId
            );
            return true;
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }

    private static boolean compileModify(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            Command<CommandSourceStack> command,
            Identifier functionId
    ) {
        if (names.size() < 7
                || !"storage".equals(names.get(2))
                || !"target".equals(names.get(3))
                || !"targetPath".equals(names.get(4))
                || !"set".equals(names.get(5))) {
            return false;
        }

        String sourceMode = names.get(6);
        if ("value".equals(sourceMode)) {
            return compileModifySetValue(context, names, command, functionId);
        }
        if ("from".equals(sourceMode)) {
            return compileModifySetFrom(context, names, command, functionId);
        }
        return false;
    }

    private static boolean compileModifySetValue(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            Command<CommandSourceStack> command,
            Identifier functionId
    ) {
        if (names.size() != 8 || !"value".equals(names.get(7))) {
            return false;
        }
        try {
            Identifier target = context.getArgument("target", Identifier.class);
            NbtPathArgument.NbtPath path = context.getArgument("targetPath", NbtPathArgument.NbtPath.class);
            Tag value = context.getArgument("value", Tag.class);
            ScoreAddPrototype.applyCommand(
                    context,
                    new DataStorageCommand(command, target, path, value, false, functionId),
                    functionId
            );
            return true;
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }

    private static boolean compileModifySetFrom(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            Command<CommandSourceStack> command,
            Identifier functionId
    ) {
        if (names.size() < 9 || !"storage".equals(names.get(7)) || !"source".equals(names.get(8))) {
            return false;
        }
        try {
            Identifier target = context.getArgument("target", Identifier.class);
            NbtPathArgument.NbtPath targetPath = context.getArgument("targetPath", NbtPathArgument.NbtPath.class);
            Identifier source = context.getArgument("source", Identifier.class);
            NbtPathArgument.NbtPath sourcePath = null;
            if (names.size() >= 10 && "sourcePath".equals(names.get(9))) {
                sourcePath = context.getArgument("sourcePath", NbtPathArgument.NbtPath.class);
            }
            ScoreAddPrototype.applyCommand(
                    context,
                    new DataCopyCommand(command, target, targetPath, source, sourcePath, functionId),
                    functionId
            );
            return true;
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }
}
