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

        // The vanilla redirect modifier bakes the unless negation into its
        // pass/fail result (ExecuteCommand.addConditional routes through
        // expect(ctx, unless, test), which passes when test == unless), so the
        // evaluator undoes that negation and reports the raw predicate result.
        // The command's unless flag then applies the inversion exactly once,
        // matching the raw-argument evaluators in PredicateModifierParser.
        final boolean negatedRedirect = unless;
        PredicateConditionCommand.PredicateEvaluator evaluator = source -> {
            try {
                Collection<CommandSourceStack> result = redirect.apply(context.copyFor(source));
                boolean passed = result != null && !result.isEmpty();
                return negatedRedirect ? !passed : passed;
            } catch (CommandSyntaxException e) {
                return null;
            }
        };

        return new PredicateModifierParser.ParsedPredicate(evaluator, unless);
    }
}
