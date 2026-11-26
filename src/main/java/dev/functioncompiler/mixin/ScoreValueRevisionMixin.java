package dev.functioncompiler.mixin;

import dev.functioncompiler.ScoreValueRevisionAccess;
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

import java.util.HashMap;
import java.util.Map;

/**
 * Records *all* normal API changes to watched scoreboard values, including
 * changes initiated synchronously by score listeners and command callbacks.
 * Reset and objective-removal notifications invalidate values as well.
 * Does not affect ordinary execution unless the cache research mode is set.
 *
 * This is an opt-in compatibility experiment, not a guarantee about writes
 * performed by mods using reflection or direct private-data corruption.
 */
@Mixin(ServerScoreboard.class)
public abstract class ScoreValueRevisionMixin implements ScoreValueRevisionAccess {
    @Unique private static final boolean functionCompiler$enabled =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SCORE_CACHE"));
    @Unique private static final boolean functionCompiler$testObserver =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_SCORE_CACHE_TEST_OBSERVER"));
    @Unique private static final boolean functionCompiler$ir046Observer =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR046_TEST_OBSERVER"));
    @Unique private final Map<Key, Long> functionCompiler$revisions = new HashMap<>();

    @Override
    public long functionCompiler$watch(Key key) {
        if (!functionCompiler$enabled) return -1L;
        return functionCompiler$revisions.computeIfAbsent(key, ignored -> 0L);
    }

    @Unique
    private void functionCompiler$bump(Key key) {
        Long before = functionCompiler$revisions.get(key);
        if (before != null) functionCompiler$revisions.put(key, before + 1L);
    }

    @Unique
    private void functionCompiler$bumpByHolder(String holder) {
        functionCompiler$revisions.replaceAll((key, v) ->
                key.holder().equals(holder) ? v + 1 : v);
    }

    @Unique
    private void functionCompiler$bumpByObjective(String objective) {
        functionCompiler$revisions.replaceAll((key, v) ->
                key.objective().equals(objective) ? v + 1 : v);
    }

    @Inject(method = "onScoreChanged", at = @At("HEAD"))
    private void functionCompiler$scoreChanged(
            ScoreHolder owner, Objective objective, Score score, CallbackInfo ci) {
        if (functionCompiler$enabled) {
            functionCompiler$bump(new Key(owner.getScoreboardName(), objective.getName()));
        }
        // IR046 disposable synchronous adversary. Only the fixture's exact
        // cursor terminal can trigger it; set/reset radius is a different slot.
        if (functionCompiler$ir046Observer && "fc_ir".equals(objective.getName())) {
            Scoreboard board = (Scoreboard) (Object) this;
            String name = owner.getScoreboardName();
            if ("#fc046_change".equals(name) && score.value() == 0)
                board.getOrCreatePlayerScore(ScoreHolder.forNameOnly("#fc046_radius"), objective).set(6);
            if ("#fc046_remove".equals(name) && score.value() == 0)
                board.resetSinglePlayerScore(ScoreHolder.forNameOnly("#fc046_radius"), objective);
        }
        // Native test-only observer: mutate a previously watched source slot
        // *inside* a scoreboard change callback. Every vanilla/compiled arm
        // sees the same update; the cache must invalidate or fail parity.
        if (functionCompiler$testObserver
                && "#fc_ir010_trigger".equals(owner.getScoreboardName())
                && "fc_ir".equals(objective.getName())) {
            Scoreboard board = (Scoreboard) (Object) this;
            var source = board.getOrCreatePlayerScore(
                    ScoreHolder.forNameOnly("#fc_ir010_source"), objective);
            source.add(5);
        }
        if (functionCompiler$testObserver
                && "#fc_ir010_reset".equals(owner.getScoreboardName())
                && "fc_ir".equals(objective.getName())) {
            // Removing the sole row exercises the other invalidation hook:
            // onPlayerRemoved, not merely onScoreChanged.
            ((Scoreboard) (Object) this).resetSinglePlayerScore(
                    ScoreHolder.forNameOnly("#fc_ir010_source"), objective);
        }
    }

    @Inject(method = "onPlayerScoreRemoved", at = @At("HEAD"))
    private void functionCompiler$scoreRemoved(
            ScoreHolder player, Objective objective, CallbackInfo ci) {
        if (functionCompiler$enabled) {
            functionCompiler$bump(new Key(player.getScoreboardName(), objective.getName()));
        }
    }

    @Inject(method = "onPlayerRemoved", at = @At("HEAD"))
    private void functionCompiler$allScoresRemoved(ScoreHolder player, CallbackInfo ci) {
        if (functionCompiler$enabled) functionCompiler$bumpByHolder(player.getScoreboardName());
    }

    @Inject(method = "onObjectiveRemoved", at = @At("HEAD"))
    private void functionCompiler$objectiveRemoved(Objective objective, CallbackInfo ci) {
        if (functionCompiler$enabled) functionCompiler$bumpByObjective(objective.getName());
    }
}
