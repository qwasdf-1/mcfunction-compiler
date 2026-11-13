package dev.functioncompiler;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.ServerFunctionManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Optional;

public final class FunctionCompilerMod implements ModInitializer {
    public static final String MOD_ID = "function_compiler";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

    private static final Identifier PROBE_FUNCTION = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "quota_three");
    private static final Identifier PROBE_TAG = Identifier.fromNamespaceAndPath(
            "function_compiler_probe", "wrapped");
    private static final Identifier LIFECYCLE_PROBE = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "probe");
    private static final Identifier LIFECYCLE_PROBE_V2 = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "probe_v2");
    private static final Identifier LIFECYCLE_TAG = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "probe");
    private static final Identifier LIFECYCLE_MACRO = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "macro_add");
    private static final Identifier LIFECYCLE_MACRO_PAIR = Identifier.fromNamespaceAndPath(
            "function_compiler_lifecycle", "macro_pair");

    @Override
    public void onInitialize() {
        registerWholeReloadFailureProbeIfRequested();
        registerConcurrentReloadProbeIfRequested();
        LOGGER.info("Research prototype loaded; construction wrapper enabled={}",
                ProbeConfiguration.wrapperEnabled());
        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) ->
                ProbeCommands.register(dispatcher));
    }

    private static void registerConcurrentReloadProbeIfRequested() {
        String marker = System.getenv("FC_CONCURRENT_RELOAD_MARKER");
        if (marker == null || marker.isBlank()) {
            return;
        }

        try {
            Class<?> probe = Class.forName(
                    "dev.functioncompiler.reloadprobe.ConcurrentReloadProbe");
            probe.getMethod("register", String.class).invoke(null, marker);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException(
                    "Concurrent resource reload probe is enabled but its test source "
                            + "was not compiled",
                    exception);
        }
    }

    private static void registerWholeReloadFailureProbeIfRequested() {
        String marker = System.getenv("FC_RESOURCE_RELOAD_FAILURE_MARKER");
        if (marker == null || marker.isBlank()) {
            return;
        }

        try {
            Class<?> probe = Class.forName(
                    "dev.functioncompiler.reloadfailure.ReloadFailureProbe");
            probe.getMethod("register").invoke(null);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException(
                    "Whole-resource reload failure probe is enabled but its test source "
                            + "was not compiled",
                    exception);
        }
    }

    static int stats(CommandSourceStack source, String rawFunctionId) {
        Identifier functionId = Identifier.tryParse(rawFunctionId);
        if (functionId == null) {
            source.sendFailure(Component.literal("FC_STATS invalid function id " + rawFunctionId));
            return 0;
        }

        String message = "FC_STATS function=" + functionId
                + " score_add_compiled=" + ProbeMetrics.scoreAddsCompiled(functionId)
                + " fused_regions_compiled=" + ProbeMetrics.fusedRegionsCompiled(functionId)
                + " score_add_executed=" + ProbeMetrics.scoreAddsExecuted(functionId)
                + " score_add_timed_calls=" + ProbeMetrics.scoreAddTimedCalls(functionId);
        source.sendSuccess(() -> Component.literal(message), false);
        return 1;
    }

    static int run(CommandSourceStack source) {
        ServerFunctionManager manager = source.getServer().getFunctions();
        Optional<CommandFunction<CommandSourceStack>> found = manager.get(PROBE_FUNCTION);
        if (found.isEmpty()) {
            source.sendFailure(Component.literal("FC_PROBE missing function " + PROBE_FUNCTION));
            return 0;
        }

        // manager.execute joins the command's existing ExecutionContext. Its
        // queue runs after this Brigadier callback returns, so ExecutionContext
        // clears the label when that queue completes.
        ProbeRuntimeTrace.begin("quota_three");
        manager.execute(found.get(), source);

        source.sendSuccess(() -> Component.literal("FC_PROBE invoked=" + PROBE_FUNCTION), false);
        return 1;
    }

    static int measure(CommandSourceStack source, String rawFunctionId) {
        if (!ProbeConfiguration.commandCallbackMetricsEnabled()) {
            source.sendFailure(Component.literal(
                    "FC_PROBE command callback metrics are disabled"));
            return 0;
        }

        Identifier functionId = Identifier.tryParse(rawFunctionId);
        if (functionId == null) {
            source.sendFailure(Component.literal(
                    "FC_PROBE invalid function id " + rawFunctionId));
            return 0;
        }

        ServerFunctionManager manager = source.getServer().getFunctions();
        Optional<CommandFunction<CommandSourceStack>> found = manager.get(functionId);
        if (found.isEmpty()) {
            source.sendFailure(Component.literal(
                    "FC_PROBE missing function " + functionId));
            return 0;
        }

        // manager.execute adds the function to the active execution queue.
        // Begin now so the current queue's callbacks are covered even though
        // its HEAD hook has already run for the measure command.
        ProbeMetrics.beginCommandCallbackScopeUntilQueueReturn();
        manager.execute(found.get(), source);
        source.sendSuccess(() -> Component.literal("FC_PROBE measured=" + functionId), false);
        return 1;
    }

}
