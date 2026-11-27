package dev.functioncompiler.mixin;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ParsedArgument;
import java.util.Map;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(CommandContext.class)
public interface CommandContextAccessor<S> {
    // IR-018: Brigadier exposes getArgument(name,type) but no public
    // getArguments() map. Clone a validated terminal with its exact already
    // parsed argument values before prototype rewriting changes its callback.
    @Accessor("arguments")
    Map<String, ParsedArgument<S, ?>> functionCompiler$getArguments();

    @Mutable
    @Accessor("command")
    void functionCompiler$setCommand(Command<S> command);
}
