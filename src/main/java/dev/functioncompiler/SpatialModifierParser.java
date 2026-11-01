package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.coordinates.SwizzleArgument;
import net.minecraft.commands.arguments.coordinates.Vec3Argument;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

import java.util.EnumSet;
import java.util.List;

final class SpatialModifierParser {
    private SpatialModifierParser() {
    }

    static ContextModifierCommand.Transformation parseInModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() != 3 || !"dimension".equals(names.get(2))) {
            return null;
        }
        try {
            Identifier dimId = context.getArgument("dimension", Identifier.class);
            ResourceKey<Level> dimKey = ResourceKey.create(Registries.DIMENSION, dimId);
            return (ctx, source) -> {
                if (source.getServer() == null) {
                    return null;
                }
                ServerLevel level = source.getServer().getLevel(dimKey);
                return level == null ? null : source.withLevel(level);
            };
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    static ContextModifierCommand.Transformation parseAlignModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() != 3 || !"axes".equals(names.get(2))) {
            return null;
        }
        try {
            EnumSet<Direction.Axis> axes = SwizzleArgument.getSwizzle(context, "axes");
            return (ctx, source) -> source.withPosition(source.getPosition().align(axes));
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    static ContextModifierCommand.Transformation parseFacingModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() != 3 || !"pos".equals(names.get(2))) {
            return null;
        }
        try {
            Vec3 pos = Vec3Argument.getVec3(context, "pos");
            return (ctx, source) -> source.facing(pos);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }
}
