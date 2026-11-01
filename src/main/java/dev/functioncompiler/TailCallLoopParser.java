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

final class TailCallLoopParser {
    private TailCallLoopParser() {
    }

    static boolean compile(CommandContext<CommandSourceStack> context, Identifier parentFunctionId) {
        Command<CommandSourceStack> command = context.getCommand();
        if (command == null || command instanceof FusableCommand || parentFunctionId == null) {
            return false;
        }

        PlainTextFunction<CommandSourceStack> plain = resolveSelf(context, parentFunctionId);
        if (plain == null) {
            return false;
        }

        ScoreAddPrototype.applyCommand(
                context,
                new TailCallLoopCommand(command, plain, parentFunctionId),
                parentFunctionId
        );
        return true;
    }

    @SuppressWarnings("unchecked")
    private static PlainTextFunction<CommandSourceStack> resolveSelf(
            CommandContext<CommandSourceStack> context,
            Identifier parentFunctionId
    ) {
        CommandFunction<CommandSourceStack> func = lookupTargetFunction(context, parentFunctionId);
        if (func instanceof PlainTextFunction<?> plain
                && isEligibleLoop((PlainTextFunction<CommandSourceStack>) plain)) {
            return (PlainTextFunction<CommandSourceStack>) plain;
        }
        return null;
    }

    private static CommandFunction<CommandSourceStack> lookupTargetFunction(
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
        if (targetId == null || !targetId.equals(parentFunctionId) || source == null || source.getServer() == null) {
            return null;
        }
        return source.getServer().getFunctions().get(targetId).orElse(null);
    }

    private static boolean isEligibleLoop(PlainTextFunction<CommandSourceStack> plain) {
        List<UnboundEntryAction<CommandSourceStack>> entries = plain.entries();
        if (entries.size() < 2 || entries.size() > 64) {
            return false;
        }
        for (int i = 0; i < entries.size() - 1; i++) {
            if (!isSafePrefixEntry(entries.get(i))) {
                return false;
            }
        }
        return true;
    }

    private static boolean isSafePrefixEntry(UnboundEntryAction<CommandSourceStack> entry) {
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
        return !"return".equals(root);
    }
}
