package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.ParticleCommand;
import net.minecraft.server.commands.PlaySoundCommand;

import java.util.List;

final class VisualSoundParser {
    private VisualSoundParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier functionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand) {
            return false;
        }

        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (isVisualSoundCommand(context, names)) {
            ScoreAddPrototype.applyCommand(
                    context,
                    new StateMachineCommand(command, functionId),
                    functionId
            );
            return true;
        }
        return false;
    }

    private static boolean isVisualSoundCommand(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.isEmpty()) {
            return false;
        }
        String root = names.get(0);
        if (!"particle".equals(root) && !"playsound".equals(root)) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null) {
            return false;
        }
        Class<?> nestHost = command.getClass().getNestHost();
        return nestHost == ParticleCommand.class || nestHost == PlaySoundCommand.class;
    }
}
