package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.data.DataCommands;

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
            ScoreAddPrototype.applyCommand(
                    context,
                    new DataGetCommand(command, functionId),
                    functionId
            );
            return true;
        }
        return false;
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
