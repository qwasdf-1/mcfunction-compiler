package dev.functioncompiler.mixin;

import net.minecraft.server.ServerScoreboard;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.Score;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Disposable IR046/047 synchronous lifecycle adversaries, fixture build only. */
@Mixin(ServerScoreboard.class)
abstract class ScoreLifecycleFixtureMixin {
    @Unique private static final boolean functionCompiler$ir046Observer =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR046_TEST_OBSERVER"));
    @Unique private static final boolean functionCompiler$ir047Observer =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR047_TEST_OBSERVER"));

    @Inject(method = "onScoreChanged", at = @At("HEAD"))
    private void functionCompiler$scoreChanged(ScoreHolder owner, Objective objective, Score score, CallbackInfo ci) {
        if (!"fc_ir".equals(objective.getName())) return;
        Scoreboard board = (Scoreboard) (Object) this;
        String name = owner.getScoreboardName();
        if (functionCompiler$ir047Observer && "#fc047_drop".equals(name) && score.value() == 0) {
            Objective removed = board.getObjective("fc047_guard");
            if (removed != null) board.removeObjective(removed);
        }
        if (functionCompiler$ir046Observer && score.value() == 0) {
            if ("#fc046_change".equals(name))
                board.getOrCreatePlayerScore(ScoreHolder.forNameOnly("#fc046_radius"), objective).set(6);
            if ("#fc046_remove".equals(name))
                board.resetSinglePlayerScore(ScoreHolder.forNameOnly("#fc046_radius"), objective);
        }
    }
}
