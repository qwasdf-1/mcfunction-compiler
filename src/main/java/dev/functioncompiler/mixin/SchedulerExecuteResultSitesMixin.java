package dev.functioncompiler.mixin;

import dev.functioncompiler.SchedulerResultSiteTrace;
import net.minecraft.server.commands.ExecuteCommand;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Four exact CommandResultCallback-producing synthetic lambda implementations
 * verified by javap for Minecraft 26.3. This is the /execute COMMAND class,
 * not the separate queue task net.minecraft.commands.execution.tasks.ExecuteCommand.
 *
 * Every entry only sets an opt-in sampled site label; neither command result
 * nor any scoreboard, bossbar, NBT or function-condition side effect changes.
 * Private compiler-generated lambda names are version-specific and fail
 * closed if removed in an incompatible Minecraft build.
 */
@Mixin(ExecuteCommand.class)
abstract class SchedulerExecuteResultSitesMixin {
    @Inject(method = "lambda$storeValue$0", at = @At("HEAD"), require = 1, remap = false)
    private static void functionCompiler$observeScoreStore(CallbackInfo ci) {
        SchedulerResultSiteTrace.observeSite(SchedulerResultSiteTrace.Site.SCORE_STORE);
    }

    @Inject(method = "lambda$storeValue$1", at = @At("HEAD"), require = 1, remap = false)
    private static void functionCompiler$observeBossbarStore(CallbackInfo ci) {
        SchedulerResultSiteTrace.observeSite(SchedulerResultSiteTrace.Site.BOSSBAR_STORE);
    }

    @Inject(method = "lambda$storeData$0", at = @At("HEAD"), require = 1, remap = false)
    private static void functionCompiler$observeDataStore(CallbackInfo ci) {
        SchedulerResultSiteTrace.observeSite(SchedulerResultSiteTrace.Site.DATA_STORE);
    }

    @Inject(method = "lambda$scheduleFunctionConditionsAndTest$0",
            at = @At("HEAD"), require = 1, remap = false)
    private static void functionCompiler$observeFunctionCondition(CallbackInfo ci) {
        SchedulerResultSiteTrace.observeSite(SchedulerResultSiteTrace.Site.FUNCTION_CONDITION);
    }
}
