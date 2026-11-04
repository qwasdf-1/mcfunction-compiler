package dev.functioncompiler.mixin;

import dev.functioncompiler.FunctionCoverageReport;
import dev.functioncompiler.ProbeConfiguration;
import net.minecraft.server.ServerFunctionLibrary;
import net.minecraft.server.packs.resources.PreparableReloadListener;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * Emits the consolidated datapack coverage report once per function-library load.
 *
 * {@code ServerFunctionLibrary.reload} resolves every function resource from every
 * loaded datapack and builds each one through {@code FunctionBuilder.build}; the
 * future it returns completes only after all of those futures have been joined and
 * the new function map is assigned. Attaching the report to that completion gives a
 * single emission per load (initial or reloaded) with a complete per-namespace
 * picture, which is what keeps a load of thousands of functions from spamming the
 * log with one line per function.
 */
@Mixin(ServerFunctionLibrary.class)
abstract class ServerFunctionLibraryMixin {
    @Inject(method = "reload", at = @At("RETURN"), cancellable = true)
    private void functionCompiler$reportCoverageOnCompletion(
            PreparableReloadListener.SharedState sharedState,
            Executor executor,
            PreparableReloadListener.PreparationBarrier barrier,
            Executor executor2,
            CallbackInfoReturnable<CompletableFuture<?>> callback
    ) {
        if (!ProbeConfiguration.wrapperEnabled()) {
            return;
        }
        CompletableFuture<?> original = callback.getReturnValue();
        callback.setReturnValue(original.whenComplete((result, error) -> {
            if (error == null) {
                FunctionCoverageReport.logReloadReport();
            }
        }));
    }
}
