package dev.functioncompiler;

import com.mojang.brigadier.RedirectModifier;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;

import java.util.Collection;
import java.util.List;

final class ItemPredicateParser {
    private ItemPredicateParser() {
    }

    static PredicateModifierParser.ParsedPredicate parse(CommandContext<CommandSourceStack> context) {
        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (names.size() < 3 || !"execute".equals(names.get(0))) {
            return null;
        }
        String modifier = names.get(1);
        boolean unless;
        if ("if".equals(modifier)) {
            unless = false;
        } else if ("unless".equals(modifier)) {
            unless = true;
        } else {
            return null;
        }

        if (!"items".equals(names.get(2))) {
            return null;
        }

        RedirectModifier<CommandSourceStack> redirect = context.getRedirectModifier();
        if (redirect == null) {
            return null;
        }

        PredicateConditionCommand.PredicateEvaluator evaluator = source -> {
            try {
                Collection<CommandSourceStack> result = redirect.apply(context.copyFor(source));
                return result != null && !result.isEmpty();
            } catch (CommandSyntaxException e) {
                return null;
            }
        };

        return new PredicateModifierParser.ParsedPredicate(evaluator, unless);
    }
}
