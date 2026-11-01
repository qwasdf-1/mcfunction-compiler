package dev.functioncompiler.reloadprobe;

import net.fabricmc.fabric.api.resource.IdentifiableResourceReloadListener;
import net.fabricmc.fabric.api.resource.ResourceManagerHelper;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.Commands;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.server.packs.resources.SimplePreparableReloadListener;
import net.minecraft.util.profiling.ProfilerFiller;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;

public final class ConcurrentReloadProbe {
    private static final long MAX_WAIT_MILLIS = 120_000;

    private ConcurrentReloadProbe() {
    }

    public static void register(String configuredMarker) {
        Path trigger = Path.of(configuredMarker);
        Path armed = sibling(trigger, ".armed");
        try {
            Files.writeString(
                    armed,
                    "ready\n",
                    StandardOpenOption.CREATE,
                    StandardOpenOption.TRUNCATE_EXISTING);
        } catch (IOException exception) {
            throw new IllegalStateException("Could not arm concurrent reload probe", exception);
        }

        ResourceManagerHelper.get(PackType.SERVER_DATA).registerReloadListener(
                new GateListener(trigger));
        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) ->
                dispatcher.register(Commands.literal("fc_test_reload_async").executes(context -> {
                    MinecraftServer server = context.getSource().getServer();
                    List<String> selectedPacks = List.copyOf(
                            server.getPackRepository().getSelectedIds());
                    Thread reloadThread = new Thread(
                            () -> server.reloadResources(selectedPacks),
                            "function-compiler-concurrent-reload-probe");
                    reloadThread.setDaemon(true);
                    reloadThread.start();
                    return 1;
                })));
    }

    private static Path sibling(Path trigger, String suffix) {
        return trigger.resolveSibling(trigger.getFileName() + suffix);
    }

    private static final class GateListener extends SimplePreparableReloadListener<Boolean>
            implements IdentifiableResourceReloadListener {
        private final Path trigger;

        private GateListener(Path trigger) {
            this.trigger = trigger;
        }

        @Override
        public Identifier getFabricId() {
            return Identifier.fromNamespaceAndPath(
                    "function_compiler_reload_probe", "concurrent_prepare_gate");
        }

        @Override
        protected Boolean prepare(ResourceManager manager, ProfilerFiller profiler) {
            try {
                if (!Files.deleteIfExists(trigger)) {
                    return false;
                }

                Path entered = sibling(trigger, ".entered");
                Path release = sibling(trigger, ".release");
                Files.writeString(
                        entered,
                        "preparation paused before reload publication\n",
                        StandardOpenOption.CREATE,
                        StandardOpenOption.TRUNCATE_EXISTING);
                long deadline = System.nanoTime() + MAX_WAIT_MILLIS * 1_000_000;
                while (!Files.exists(release)) {
                    if (System.nanoTime() >= deadline) {
                        throw new IllegalStateException(
                                "Timed out waiting for concurrent reload probe release: "
                                        + release);
                    }
                    try {
                        Thread.sleep(10);
                    } catch (InterruptedException exception) {
                        Thread.currentThread().interrupt();
                        throw new IllegalStateException(
                                "Concurrent reload probe was interrupted", exception);
                    }
                }
                Files.deleteIfExists(release);
                return true;
            } catch (IOException exception) {
                throw new IllegalStateException("Could not run concurrent reload probe", exception);
            }
        }

        @Override
        protected void apply(Boolean paused, ResourceManager manager, ProfilerFiller profiler) {
        }
    }
}
