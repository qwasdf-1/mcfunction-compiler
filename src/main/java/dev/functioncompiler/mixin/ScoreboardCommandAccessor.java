package dev.functioncompiler.mixin;

import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.server.commands.ScoreboardCommand;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(ScoreboardCommand.class)
public interface ScoreboardCommandAccessor {
    @Accessor("RESPONSE_SCORE_ADD")
    static CommandResponseTracker.MessagesWithArgs<ScoreHolder, Objective, Integer>
    functionCompiler$getScoreAddResponse() {
        throw new AssertionError();
    }

    @Accessor("RESPONSE_SCORE_SET")
    static CommandResponseTracker.MessagesWithArgs<ScoreHolder, Objective, Integer>
    functionCompiler$getScoreSetResponse() {
        throw new AssertionError();
    }

    @Accessor("RESPONSE_SCORE_REMOVE")
    static CommandResponseTracker.MessagesWithArgs<ScoreHolder, Objective, Integer>
    functionCompiler$getScoreRemoveResponse() {
        throw new AssertionError();
    }

    @Accessor("RESPONSE_SCORE_OPERATION")
    static CommandResponseTracker.MessagesWithArg<ScoreHolder, Objective>
    functionCompiler$getScoreOperationResponse() {
        throw new AssertionError();
    }

    @Accessor("RESPONSE_SCORE_RESET")
    static CommandResponseTracker.MessagesWithArg<ScoreHolder, Objective>
    functionCompiler$getScoreResetResponse() {
        throw new AssertionError();
    }

    @Accessor("RESPONSE_SCORE_RESET_ALL")
    static CommandResponseTracker.Messages<ScoreHolder>
    functionCompiler$getScoreResetAllResponse() {
        throw new AssertionError();
    }
}
