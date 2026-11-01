package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.KillCommand;
import net.minecraft.server.commands.TagCommand;
import net.minecraft.server.commands.TeleportCommand;

import java.util.List;

final class StateMachineParser {
    private StateMachineParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier functionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand) {
            return false;
        }

        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (isTagCommand(context, names)
                || isTeleportCommand(context, names)
                || isKillCommand(context, names)) {
            ScoreAddPrototype.applyCommand(
                    context,
                    new StateMachineCommand(command, functionId),
                    functionId
            );
            return true;
        }
        return false;
    }

    private static boolean isTagCommand(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() != 4 || !"tag".equals(names.get(0)) || !"targets".equals(names.get(1))) {
            return false;
        }
        String action = names.get(2);
        if (!"add".equals(action) && !"remove".equals(action)) {
            return false;
        }
        if (!"name".equals(names.get(3))) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        return command != null && command.getClass().getNestHost() == TagCommand.class;
    }

    private static boolean isTeleportCommand(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.isEmpty()) {
            return false;
        }
        String root = names.get(0);
        if (!"teleport".equals(root) && !"tp".equals(root)) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        return command != null && command.getClass().getNestHost() == TeleportCommand.class;
    }

    private static boolean isKillCommand(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.isEmpty() || !"kill".equals(names.get(0))) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        return command != null && command.getClass().getNestHost() == KillCommand.class;
    }
}
