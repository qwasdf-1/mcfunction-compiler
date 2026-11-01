package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;

import java.util.List;
import java.util.Optional;

final class LeafFunctionParser {
    private LeafFunctionParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier parentFunctionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand) {
            return false;
        }

        PlainTextFunction<CommandSourceStack> plain = resolveTarget(context, parentFunctionId);
        if (plain == null) {
            return false;
        }

        ScoreAddPrototype.applyCommand(
                context,
                new InlinedFunctionCommand(command, plain, parentFunctionId),
                parentFunctionId
        );
        return true;
    }

    private static PlainTextFunction<CommandSourceStack> resolveTarget(
            CommandContext<CommandSourceStack> context,
            Identifier parentFunctionId
    ) {
        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (names.size() != 2 || !"function".equals(names.get(0)) || !"name".equals(names.get(1))) {
            return null;
        }

        String targetText = ScoreAddPrototype.extractNodeText(context, "name");
        Identifier targetId = targetText == null ? null : Identifier.tryParse(targetText);
        CommandSourceStack source = context.getSource();
        if (targetId == null || targetId.equals(parentFunctionId) || source == null || source.getServer() == null) {
            return null;
        }

        Optional<CommandFunction<CommandSourceStack>> optionalFunc =
                source.getServer().getFunctions().get(targetId);
        if (optionalFunc.isEmpty() || !isPureLeaf(optionalFunc.get())) {
            return null;
        }

        @SuppressWarnings("unchecked")
        PlainTextFunction<CommandSourceStack> plain =
                (PlainTextFunction<CommandSourceStack>) optionalFunc.get();
        return plain;
    }

    private static boolean isPureLeaf(CommandFunction<CommandSourceStack> function) {
        if (!(function instanceof PlainTextFunction<CommandSourceStack> plain)) {
            return false;
        }
        List<UnboundEntryAction<CommandSourceStack>> entries = plain.entries();
        if (entries.isEmpty() || entries.size() > 64) {
            return false;
        }
        for (UnboundEntryAction<CommandSourceStack> entry : entries) {
            if (!isEntryLeaf(entry)) {
                return false;
            }
        }
        return true;
    }

    private static boolean isEntryLeaf(UnboundEntryAction<CommandSourceStack> entry) {
        if (!(entry instanceof BuildContextsAccessor<?> bca)) {
            return false;
        }
        @SuppressWarnings("unchecked")
        var chain = ((BuildContextsAccessor<CommandSourceStack>) (Object) bca).functionCompiler$getCommand();
        List<String> names = ScoreAddPrototype.nodeNames(chain.getTopContext());
        if (names.isEmpty()) {
            return false;
        }
        String root = names.get(0);
        return !"function".equals(root) && !"return".equals(root);
    }
}
