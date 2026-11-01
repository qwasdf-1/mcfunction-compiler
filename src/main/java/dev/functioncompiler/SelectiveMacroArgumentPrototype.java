package dev.functioncompiler;

import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.commands.arguments.item.FunctionArgument;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.MacroFunction;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.commands.data.DataAccessor;
import net.minecraft.server.commands.data.StorageDataAccessor;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.component.CustomData;
import dev.functioncompiler.mixin.CustomDataAccessor;
import dev.functioncompiler.mixin.EntityDataAccessorAccessor;
import dev.functioncompiler.mixin.MacroFunctionAccessor;

import java.util.Collection;
import java.util.List;

/**
 * Disabled-by-default prototype for avoiding full entity or storage serialization
 * when a single macro function reads a small set of top-level custom-data or storage fields.
 */
public final class SelectiveMacroArgumentPrototype {
    private SelectiveMacroArgumentPrototype() {
    }

    public static CompoundTag tryBuild(
            NbtPathArgument.NbtPath path,
            DataAccessor dataAccessor,
            CommandContext<CommandSourceStack> context
    ) throws CommandSyntaxException {
        CompoundTag source = resolveSourceCompound(path, dataAccessor);
        if (source == null) {
            return null;
        }

        List<String> parameters = resolveMacroParameters(context);
        if (parameters == null || parameters.isEmpty()) {
            return null;
        }

        return buildSelected(source, parameters);
    }

    private static CompoundTag resolveSourceCompound(
            NbtPathArgument.NbtPath path,
            DataAccessor dataAccessor
    ) {
        if (dataAccessor instanceof EntityDataAccessorAccessor entityAccessor) {
            return resolveEntitySource(path, entityAccessor);
        }
        if (dataAccessor instanceof StorageDataAccessor storageAccessor) {
            return resolveStorageSource(path, storageAccessor);
        }
        return null;
    }

    private static CompoundTag resolveEntitySource(
            NbtPathArgument.NbtPath path,
            EntityDataAccessorAccessor entityAccessor
    ) {
        if (!"data".equals(path.asString())) {
            return null;
        }
        Entity entity = entityAccessor.functionCompiler$getEntity();
        CustomData customData = entity.get(DataComponents.CUSTOM_DATA);
        if (customData == null || customData.isEmpty()) {
            return null;
        }
        return ((CustomDataAccessor) (Object) customData).functionCompiler$getTag();
    }

    private static CompoundTag resolveStorageSource(
            NbtPathArgument.NbtPath path,
            StorageDataAccessor storageAccessor
    ) {
        try {
            List<Tag> tags = path.get(storageAccessor.getData());
            if (tags.size() == 1 && tags.get(0) instanceof CompoundTag compound) {
                return compound;
            }
        } catch (CommandSyntaxException exception) {
            return null;
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static List<String> resolveMacroParameters(
            CommandContext<CommandSourceStack> context
    ) {
        Collection<CommandFunction<CommandSourceStack>> functions;
        try {
            functions = FunctionArgument.getFunctionCollection(context, "name").getSecond();
        } catch (IllegalArgumentException | CommandSyntaxException exception) {
            return null;
        }
        if (functions.size() != 1) {
            return null;
        }

        CommandFunction<CommandSourceStack> function = functions.iterator().next();
        if (function instanceof ProbeFunctionWrapper<?> wrapper) {
            function = (CommandFunction<CommandSourceStack>) wrapper.delegate();
        }
        if (function.id() != null && ProbeConfiguration.isNamespaceExcluded(function.id().getNamespace())) {
            return null;
        }
        if (!(function instanceof MacroFunction<?> macroFunction)) {
            return null;
        }

        return ((MacroFunctionAccessor) macroFunction).functionCompiler$getParameters();
    }

    private static CompoundTag buildSelected(
            CompoundTag source,
            List<String> parameters
    ) {
        CompoundTag selected = new CompoundTag();
        for (String parameter : parameters) {
            Tag value = source.get(parameter);
            if (value == null) {
                return null;
            }
            selected.put(parameter, value.copy());
        }

        if (ProbeConfiguration.selectiveMacroArgumentsMetricsEnabled()) {
            ProbeMetrics.selectiveMacroArgumentsUsed();
        }
        return selected;
    }
}
