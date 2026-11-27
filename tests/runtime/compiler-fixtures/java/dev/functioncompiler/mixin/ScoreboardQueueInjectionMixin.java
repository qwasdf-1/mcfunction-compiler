package dev.functioncompiler.mixin;

import dev.functioncompiler.ReentrantQueueProbe;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.ServerScoreboard;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.Score;
import net.minecraft.world.scores.ScoreHolder;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** IR-013 test-only callback; the helper itself is a disabled-by-default no-op. */
@Mixin(ServerScoreboard.class)
abstract class ScoreboardQueueInjectionMixin {
    @Shadow @Final private MinecraftServer server;

    @Inject(method = "onScoreChanged", at = @At("HEAD"))
    private void functionCompiler$injectReentrantQueue(
            ScoreHolder owner, Objective objective, Score score, CallbackInfo callback
    ) {
        ReentrantQueueProbe.scoreChanged(server, owner, objective);
    }
}
