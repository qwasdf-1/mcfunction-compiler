package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.selector.EntitySelector;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;

import java.util.List;

final class ForkModifierParser {
    @FunctionalInterface
    interface CandidateResolver {
        List<? extends Entity> resolve(CommandSourceStack source) throws CommandSyntaxException;
    }

    @FunctionalInterface
    interface ForkTransformer {
        CommandSourceStack transform(CommandSourceStack source, Entity entity);
    }

    static final ForkTransformer FORK_AS = CommandSourceStack::withEntity;

    static final ForkTransformer FORK_AT = (source, entity) ->
            source.withLevel((ServerLevel) entity.level())
                    .withPosition(entity.position())
                    .withRotation(entity.getRotationVector());

    static final ForkTransformer FORK_ON = CommandSourceStack::withEntity;

    record ParsedFork(CandidateResolver resolver, ForkTransformer transformer) {
    }

    private ForkModifierParser() {
    }

    static ParsedFork parse(CommandContext<CommandSourceStack> context) {
        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (names.size() < 3 || !"execute".equals(names.get(0))) {
            return null;
        }

        String sub = names.get(1);
        if ("as".equals(sub)) {
            return parseSelectorFork(context, names, FORK_AS);
        }
        if ("at".equals(sub)) {
            return parseSelectorFork(context, names, FORK_AT);
        }
        if ("on".equals(sub)) {
            return parseRelationFork(names.get(2));
        }
        return null;
    }

    private static ParsedFork parseSelectorFork(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            ForkTransformer transformer
    ) {
        if (names.size() != 3 || !"targets".equals(names.get(2))) {
            return null;
        }
        if ("@s".equals(ScoreAddPrototype.extractNodeText(context, "targets"))) {
            return null;
        }
        try {
            EntitySelector selector = context.getArgument("targets", EntitySelector.class);
            return new ParsedFork(selector::findEntities, transformer);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    private static ParsedFork parseRelationFork(String relationName) {
        EntityRelation relation = EntityRelation.fromName(relationName);
        if (relation == null) {
            return null;
        }
        CandidateResolver resolver = source -> {
            Entity entity = source.getEntity();
            return entity == null ? List.of() : relation.resolve(entity);
        };
        return new ParsedFork(resolver, FORK_ON);
    }
}
