package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Marker;

/**
 * IR-023 test-only mutation route. Calls the original live mutable backing
 * Set exposed by Entity.entityTags(), not the public addTag/removeTag methods.
 * The fixture deliberately demonstrates a route invisible to IR023's
 * addTag/removeTag-only invalidation observation. Never registered unless
 * explicitly enabled by the native test harness environment flag.
 */
final class CompilerTagVisibility023Harness {
    private CompilerTagVisibility023Harness() {}

    static int mutate(CommandSourceStack source, String tag, boolean add)
            throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        Entity entity = source.getEntityOrException();
        if (!(entity instanceof Marker)
                || !entity.entityTags().contains("fc023.fixture")
                || (!"erb.block".equals(tag) && !"erb.verified".equals(tag))) {
            return 0;
        }
        boolean changed = add ? entity.entityTags().add(tag)
                              : entity.entityTags().remove(tag);
        return changed ? 1 : 0;
    }
}
