package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.ClearInventoryCommands;
import net.minecraft.server.commands.DamageCommand;
import net.minecraft.server.commands.GiveCommand;
import net.minecraft.server.commands.RotateCommand;
import net.minecraft.server.commands.SummonCommand;

import java.util.List;
import java.util.Set;

final class GameplayCommandParser {
    private static final Set<String> ROOTS = Set.of("summon", "damage", "give", "clear", "rotate");
    private static final Set<Class<?>> HOSTS = Set.of(
            SummonCommand.class,
            DamageCommand.class,
            GiveCommand.class,
            ClearInventoryCommands.class,
            RotateCommand.class
    );

    private GameplayCommandParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier functionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand) {
            return false;
        }

        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (isGameplayCommand(command, names)) {
            ScoreAddPrototype.applyCommand(
                    context,
                    new StateMachineCommand(command, functionId),
                    functionId
            );
            return true;
        }
        return false;
    }

    private static boolean isGameplayCommand(
            Command<CommandSourceStack> command,
            List<String> names
    ) {
        if (names.isEmpty() || !ROOTS.contains(names.get(0))) {
            return false;
        }
        return HOSTS.contains(command.getClass().getNestHost());
    }
}
