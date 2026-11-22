package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.data.DataCommands;
import net.minecraft.commands.arguments.NbtPathArgument;

import java.util.List;

final class DataGetParser {
    private DataGetParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier functionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand) {
            return false;
        }

        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (isDataGetCommand(context, names)) {
            int positionAxis = ir030PositionAxis(context, functionId, names);
            if (positionAxis >= 0) {
                NbtPathArgument.NbtPath path =
                        NbtPathArgument.getPath(context, "path");
                ScoreAddPrototype.applyCommand(
                        context,
                        new EntityPosGetCommand(
                                new DataGetCommand(command, functionId),
                                path, positionAxis),
                        functionId
                );
            } else {
                ScoreAddPrototype.applyCommand(
                        context,
                        new DataGetCommand(command, functionId),
                        functionId
                );
            }
            return true;
        }
        return false;
    }

    private static int ir030PositionAxis(
            CommandContext<CommandSourceStack> context,
            Identifier functionId,
            List<String> names
    ) {
        if (!ProbeConfiguration.ir030PosGetForFunction(functionId)
                || names.size() != 5
                || !List.of("data", "get", "entity", "target", "path").equals(names)
                || !"@s".equals(ScoreAddPrototype.extractNodeText(context, "target"))) {
            return -1;
        }
        String input = context.getInput();
        if (!"vm:queue/append_here".equals(functionId.toString())
                && !"function_compiler_probe:ir030_pos_store".equals(functionId.toString())
                && !"function_compiler_probe:ir030_missing_path".equals(functionId.toString())) {
            return -1;
        }
        NbtPathArgument.NbtPath path;
        try {
            path = NbtPathArgument.getPath(context, "path");
        } catch (IllegalArgumentException exception) {
            return -1;
        }
        String pathText = path.asString();
        for (int axis = 0; axis < 3; axis++) {
            String suffix = "Pos[" + axis + "]";
            String expected = "execute store result entity @s data.frontier[-1]."
                    + "xyz".charAt(axis) + " int 1 run data get entity @s " + suffix;
            if (suffix.equals(pathText) && expected.equals(input)) {
                return axis;
            }
        }
        return -1;
    }

    private static boolean isDataGetCommand(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() < 3 || !"data".equals(names.get(0)) || !"get".equals(names.get(1))) {
            return false;
        }
        String targetType = names.get(2);
        if (!"storage".equals(targetType) && !"entity".equals(targetType) && !"block".equals(targetType)) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        return command != null && command.getClass().getNestHost() == DataCommands.class;
    }
}
