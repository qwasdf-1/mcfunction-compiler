package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.nbt.ByteTag;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.DoubleTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.IntTag;
import net.minecraft.nbt.LongTag;
import net.minecraft.nbt.ShortTag;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.storage.CommandStorage;

import java.util.Map;
import java.util.function.DoubleFunction;

final class DataStoreCommand implements FusableCommand {
    enum NumericType {
        BYTE(v -> ByteTag.valueOf((byte) (int) v)),
        SHORT(v -> ShortTag.valueOf((short) (int) v)),
        INT(v -> IntTag.valueOf((int) v)),
        LONG(v -> LongTag.valueOf((long) v)),
        FLOAT(v -> FloatTag.valueOf((float) v)),
        DOUBLE(DoubleTag::valueOf);

        private static final Map<String, NumericType> LOOKUP = Map.of(
                "byte", BYTE,
                "short", SHORT,
                "int", INT,
                "long", LONG,
                "float", FLOAT,
                "double", DOUBLE
        );

        private final DoubleFunction<Tag> factory;

        NumericType(DoubleFunction<Tag> factory) {
            this.factory = factory;
        }

        Tag create(double v) {
            return factory.apply(v);
        }

        static NumericType fromName(String name) {
            return LOOKUP.getOrDefault(name, DOUBLE);
        }
    }

    private final ContextChain<CommandSourceStack> fallbackChain;
    private final Identifier storageId;
    private final NbtPathArgument.NbtPath path;
    private final NumericType type;
    private final double scale;
    private final boolean isResult;
    private final Command<CommandSourceStack> innerCommand;
    private final Identifier functionId;

    DataStoreCommand(
            ContextChain<CommandSourceStack> fallbackChain,
            Identifier storageId,
            NbtPathArgument.NbtPath path,
            NumericType type,
            double scale,
            boolean isResult,
            Command<CommandSourceStack> innerCommand,
            Identifier functionId
    ) {
        this.fallbackChain = fallbackChain;
        this.storageId = storageId;
        this.path = path;
        this.type = type;
        this.scale = scale;
        this.isResult = isResult;
        this.innerCommand = innerCommand;
        this.functionId = functionId;
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context) throws CommandSyntaxException {
        if (ProbeConfiguration.scoreAddTimingEnabled()) {
            long started = System.nanoTime();
            try {
                return runUntimed(context);
            } finally {
                ProbeMetrics.scoreAddTimed(functionId, System.nanoTime() - started);
            }
        }
        return runUntimed(context);
    }

    private int runUntimed(CommandContext<CommandSourceStack> context)
            throws CommandSyntaxException {
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()) {
            return fallbackChain.executeAll(
                    context.getSource(),
                    ExecutionCommandSource.resultConsumer()
            );
        }

        int result;
        try {
            result = innerCommand.run(context);
        } catch (CommandSyntaxException exception) {
            if (isResult) {
                throw exception;
            }
            writeStoredValue(context.getSource(), 0);
            throw exception;
        }

        int val = isResult ? result : 1;
        writeStoredValue(context.getSource(), val);

        CommandSourceStack source = context.getSource();
        if (source.callback() != null) {
            source.callback().onResult(true, result);
        }

        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }

    private void writeStoredValue(CommandSourceStack source, int val) {
        CommandStorage storage = source.getServer().getCommandStorage();
        CompoundTag tag = storage.get(storageId);
        Tag tagVal = type.create(val * scale);
        try {
            path.set(tag, tagVal);
            storage.set(storageId, tag);
        } catch (CommandSyntaxException ignored) {
        }
    }
}
