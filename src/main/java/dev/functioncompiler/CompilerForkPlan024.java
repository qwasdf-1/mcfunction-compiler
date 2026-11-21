package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.ContextChainAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.selector.EntitySelector;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;

import java.util.List;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * IR-024 compiler-owned, post-Brigadier fork plan ADMISSION ONLY.
 *
 * Native EntitySelector object is taken from the ORIGINAL parsed Brigadier
 * redirect, not rebuilt by reparsing the input string. The source shape
 * constrains the proposed backend. The two original parsed modifier stages
 * and terminal must also be present; mismatches fail to the opaque original.
 *
 * NO selector acceleration, index, cached result, alternate queue, source
 * substitution or compiled execute-as code is installed by this class.
 * MixedFunctionIR retains original UnboundEntryAction byte-for-byte.
 */
final class CompilerForkPlan024 {
    private static final boolean ENABLED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_NATIVE_FORK_PLAN"));
    private static final Pattern SOURCE = Pattern.compile(
            "^execute as (@e\\[[^\\s\\]]+\\]) "
            + "if score @s ([a-zA-Z0-9_.:-]+) = (#[a-zA-Z0-9_.:-]+) ([a-zA-Z0-9_.:-]+) "
            + "run scoreboard players set (#[a-zA-Z0-9_.:-]+) "
            + "([a-zA-Z0-9_.:-]+) (-?[0-9]+)$"
    );
    private CompilerForkPlan024() {}

    /**
     * Static command shape and ORIGINAL NATIVE selected syntax only.
     * Score condition is evaluated per entity at runtime, not at load time.
     */
    record Plan(
            EntitySelector nativeSelector,
            String selectorText,
            String entityScoreObjective,
            String comparisonHolder,
            String comparisonObjective,
            String mutationHolder,
            String mutationObjective,
            int mutationValue,
            String commandInput,
            CommandContext<CommandSourceStack> terminalContext
    ) {
        Plan {
            Objects.requireNonNull(nativeSelector);
            Objects.requireNonNull(selectorText);
            Objects.requireNonNull(entityScoreObjective);
            Objects.requireNonNull(comparisonHolder);
            Objects.requireNonNull(comparisonObjective);
            Objects.requireNonNull(mutationHolder);
            Objects.requireNonNull(mutationObjective);
            Objects.requireNonNull(commandInput);
            Objects.requireNonNull(terminalContext);
        }
    }

    static Plan classify(UnboundEntryAction<CommandSourceStack> original) {
        if (!ENABLED || !(original instanceof BuildContexts.Unbound<?> build)) return null;
        try {
            @SuppressWarnings("unchecked")
            BuildContextsAccessor<CommandSourceStack> access =
                    (BuildContextsAccessor<CommandSourceStack>) (Object) build;
            String source = access.functionCompiler$getCommandInput();
            if (source == null) return null;
            Matcher matcher = SOURCE.matcher(source);
            if (!matcher.matches()) return null;
            // Reject selectors outside the initial measured family, including
            // @a, @s, world-crossing or arbitrary parser suggestions.
            String selectorText = matcher.group(1);
            if (!selectorText.startsWith("@e[type=minecraft:marker,")
                    || !selectorText.contains("tag=")
                    || !selectorText.contains("tag=!")) return null;

            ContextChain<CommandSourceStack> chain = access.functionCompiler$getCommand();
            @SuppressWarnings("unchecked")
            ContextChainAccessor<CommandSourceStack> stages =
                    (ContextChainAccessor<CommandSourceStack>) (Object) chain;
            List<CommandContext<CommandSourceStack>> modifiers =
                    stages.functionCompiler$getModifiers();
            // Mapped native Brigadier parser stages are:
            // 0 [execute, as, targets]
            // 1 [if, score, target, targetObjective, =, source, sourceObjective]
            // 2 [run] -- a real parsed redirect bridge, NOT another condition.
            // Verified in original Minecraft 26.3 native IR024 diagnostics.
            if (modifiers.size() != 3
                    || !ScoreAddPrototype.nodeNames(modifiers.get(2)).equals(List.of("run")))
                return null;
            CommandContext<CommandSourceStack> as = modifiers.get(0);
            CommandContext<CommandSourceStack> condition = modifiers.get(1);
            CommandContext<CommandSourceStack> terminal =
                    stages.functionCompiler$getExecutable();
            if (terminal == null) return null;
            List<String> asNodes = ScoreAddPrototype.nodeNames(as);
            List<String> conditionNodes = ScoreAddPrototype.nodeNames(condition);
            List<String> terminalNodes = ScoreAddPrototype.nodeNames(terminal);
            if (!asNodes.equals(List.of("execute", "as", "targets"))
                    || !conditionNodes.equals(List.of("if", "score", "target",
                            "targetObjective", "=", "source", "sourceObjective"))
                    || !terminalNodes.contains("scoreboard")
                    || !terminalNodes.contains("players")
                    || !terminalNodes.contains("set")
                    || as.getRedirectModifier() == null
                    || condition.getRedirectModifier() == null
                    || !as.isForked()
                    || terminal.getCommand() == null) return null;
            // Validate source-shaped operand identities AGAINST already parsed
            // node ranges; the regex is never used to instantiate a selector
            // or invent a command argument.
            if (!selectorText.equals(ScoreAddPrototype.extractNodeText(as, "targets"))
                    || !"@s".equals(ScoreAddPrototype.extractNodeText(condition, "target"))
                    || !matcher.group(2).equals(ScoreAddPrototype.extractNodeText(
                            condition, "targetObjective"))
                    || !matcher.group(3).equals(ScoreAddPrototype.extractNodeText(
                            condition, "source"))
                    || !matcher.group(4).equals(ScoreAddPrototype.extractNodeText(
                            condition, "sourceObjective"))
                    || !matcher.group(5).equals(ScoreAddPrototype.extractNodeText(
                            terminal, "targets"))
                    || !matcher.group(6).equals(ScoreAddPrototype.extractNodeText(
                            terminal, "objective"))
                    || !matcher.group(7).equals(ScoreAddPrototype.extractNodeText(
                            terminal, "score"))) return null;
            // This is the native parser's EntitySelector object, with all
            // world permission, feature, filtering, sorting and limit logic.
            EntitySelector selector = as.getArgument("targets", EntitySelector.class);
            int value = Integer.parseInt(matcher.group(7));
            return new Plan(selector, selectorText, matcher.group(2),
                    matcher.group(3), matcher.group(4), matcher.group(5),
                    matcher.group(6), value, source, terminal);
        } catch (ClassCastException | IllegalArgumentException | NullPointerException e) {
            return null;
        }
    }

    static boolean enabled() { return ENABLED; }
}
