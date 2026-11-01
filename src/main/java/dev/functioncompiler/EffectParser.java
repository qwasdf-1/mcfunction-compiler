package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.EffectCommands;

import java.util.List;

final class EffectParser {
    private EffectParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier functionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand) {
            return false;
        }

        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (isEffectCommand(context, names)) {
            ScoreAddPrototype.applyCommand(
                    context,
                    new StateMachineCommand(command, functionId),
                    functionId
            );
            return true;
        }
        return false;
    }

    private static boolean isEffectCommand(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.isEmpty() || !"effect".equals(names.get(0))) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        return command != null && command.getClass().getNestHost() == EffectCommands.class;
    }
}
