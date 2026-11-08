package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.item.ItemCommands;

import java.util.List;

final class ItemCommandParser {
    private ItemCommandParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier functionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand) {
            return false;
        }

        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (isItemCommand(context, names)) {
            ScoreAddPrototype.applyCommand(
                    context,
                    new StateMachineCommand(command, functionId),
                    functionId
            );
            ProbeMetrics.itemCommandCompiled(functionId);
            return true;
        }
        return false;
    }

    private static boolean isItemCommand(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.isEmpty() || !"item".equals(names.get(0))) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        return command != null && command.getClass().getNestHost() == ItemCommands.class;
    }
}
