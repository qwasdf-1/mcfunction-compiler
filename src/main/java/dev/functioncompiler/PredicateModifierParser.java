package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.blocks.BlockPredicateArgument;
import net.minecraft.commands.arguments.coordinates.Coordinates;
import net.minecraft.commands.arguments.selector.EntitySelector;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.state.pattern.BlockInWorld;
import net.minecraft.world.level.storage.loot.LootContext;
import net.minecraft.world.level.storage.loot.LootParams;
import net.minecraft.world.level.storage.loot.parameters.LootContextParamSets;
import net.minecraft.world.level.storage.loot.parameters.LootContextParams;
import net.minecraft.world.level.storage.loot.predicates.LootItemCondition;

import java.util.List;
import java.util.Optional;

final class PredicateModifierParser {
    record ParsedPredicate(
            PredicateConditionCommand.PredicateEvaluator evaluator,
            boolean unless
    ) {
    }

    private PredicateModifierParser() {
    }

    static ParsedPredicate parse(CommandContext<CommandSourceStack> context) {
        List<String> names = ScoreAddPrototype.nodeNames(context);
        Boolean unless = parseUnlessFlag(names);
        if (unless == null) {
            return null;
        }
        return dispatchPredicate(context, names, unless);
    }

    private static Boolean parseUnlessFlag(List<String> names) {
        if (names.size() < 3 || !"execute".equals(names.get(0))) {
            return null;
        }
        String modifier = names.get(1);
        if ("if".equals(modifier)) {
            return Boolean.FALSE;
        }
        if ("unless".equals(modifier)) {
            return Boolean.TRUE;
        }
        return null;
    }

    private static ParsedPredicate dispatchPredicate(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            boolean unless
    ) {
        return switch (names.get(2)) {
            case "entity" -> parseEntityPredicate(context, names, unless);
            case "block" -> parseBlockPredicate(context, names, unless);
            case "predicate" -> parseCustomPredicate(context, names, unless);
            default -> null;
        };
    }

    private static ParsedPredicate parseEntityPredicate(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            boolean unless
    ) {
        if (names.size() != 4 || !"entities".equals(names.get(3))) {
            return null;
        }
        if ("@s".equals(ScoreAddPrototype.extractNodeText(context, "entities"))) {
            return new ParsedPredicate(source -> source.getEntity() != null, unless);
        }
        try {
            EntitySelector selector = context.getArgument("entities", EntitySelector.class);
            PredicateConditionCommand.PredicateEvaluator evaluator = source -> {
                try {
                    return !selector.findEntities(source).isEmpty();
                } catch (CommandSyntaxException e) {
                    return null;
                }
            };
            return new ParsedPredicate(evaluator, unless);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    private static ParsedPredicate parseBlockPredicate(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            boolean unless
    ) {
        if (names.size() != 5 || !"pos".equals(names.get(3)) || !"block".equals(names.get(4))) {
            return null;
        }
        try {
            Coordinates coordinates = context.getArgument("pos", Coordinates.class);
            BlockPredicateArgument.Result predicate =
                    context.getArgument("block", BlockPredicateArgument.Result.class);
            PredicateConditionCommand.PredicateEvaluator evaluator = source -> {
                ServerLevel level = source.getLevel();
                BlockPos pos = coordinates.getBlockPos(source);
                if (!level.hasChunkAt(pos) || !level.isInWorldBounds(pos)) {
                    return null;
                }
                return predicate.test(new BlockInWorld(level, pos, true));
            };
            return new ParsedPredicate(evaluator, unless);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    private static ParsedPredicate parseCustomPredicate(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            boolean unless
    ) {
        if (names.size() != 4 || !"predicate".equals(names.get(3))) {
            return null;
        }
        try {
            @SuppressWarnings("unchecked")
            Holder<LootItemCondition> holder =
                    (Holder<LootItemCondition>) context.getArgument("predicate", Holder.class);
            PredicateConditionCommand.PredicateEvaluator evaluator = source -> {
                ServerLevel level = source.getLevel();
                LootParams params = new LootParams.Builder(level)
                        .withParameter(LootContextParams.ORIGIN, source.getPosition())
                        .withOptionalParameter(LootContextParams.THIS_ENTITY, source.getEntity())
                        .create(LootContextParamSets.COMMAND);
                LootContext lootContext = new LootContext.Builder(params).create(Optional.empty());
                lootContext.pushVisitedElement(LootContext.createVisitedEntry(holder.value()));
                return holder.value().test(lootContext);
            };
            return new ParsedPredicate(evaluator, unless);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }
}
