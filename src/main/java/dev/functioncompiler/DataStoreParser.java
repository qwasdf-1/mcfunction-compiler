package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.resources.Identifier;

import java.util.List;

final class DataStoreParser {
    record ParsedDataStore(
            Identifier storageId,
            NbtPathArgument.NbtPath path,
            DataStoreCommand.NumericType type,
            double scale,
            boolean isResult
    ) {
    }

    private DataStoreParser() {
    }

    static ParsedDataStore parse(CommandContext<CommandSourceStack> context) {
        List<String> names = ScoreAddPrototype.nodeNames(context);
        if (names.size() != 8
                || !"execute".equals(names.get(0))
                || !"store".equals(names.get(1))) {
            return null;
        }
        String storeType = names.get(2);
        boolean isResult;
        if ("result".equals(storeType)) {
            isResult = true;
        } else if ("success".equals(storeType)) {
            isResult = false;
        } else {
            return null;
        }

        if (!"storage".equals(names.get(3))
                || !"target".equals(names.get(4))
                || !"path".equals(names.get(5))
                || !"scale".equals(names.get(7))) {
            return null;
        }

        try {
            Identifier target = context.getArgument("target", Identifier.class);
            NbtPathArgument.NbtPath path = context.getArgument("path", NbtPathArgument.NbtPath.class);
            double scale = context.getArgument("scale", Double.class);
            DataStoreCommand.NumericType type = DataStoreCommand.NumericType.fromName(names.get(6));
            return new ParsedDataStore(target, path, type, scale, isResult);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }
}
