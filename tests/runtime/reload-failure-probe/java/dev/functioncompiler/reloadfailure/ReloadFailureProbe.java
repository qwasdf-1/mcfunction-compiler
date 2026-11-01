package dev.functioncompiler.reloadfailure;

import net.fabricmc.fabric.api.resource.ResourceManagerHelper;
import net.fabricmc.fabric.api.resource.SimpleSynchronousResourceReloadListener;
import net.minecraft.resources.Identifier;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.resources.ResourceManager;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

public final class ReloadFailureProbe {
    private static final String MARKER_ENV = "FC_RESOURCE_RELOAD_FAILURE_MARKER";
    private static final String FAILURE_MESSAGE = "FC_RESOURCE_RELOAD_FAILURE_PROBE";

    public static void register() {
        String configuredMarker = System.getenv(MARKER_ENV);
        if (configuredMarker == null || configuredMarker.isBlank()) {
            return;
        }

        Path trigger = Path.of(configuredMarker);
        Path armed = trigger.resolveSibling(trigger.getFileName() + ".armed");
        try {
            Files.writeString(
                armed,
                "ready\n",
                StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING
            );
        } catch (IOException exception) {
            throw new IllegalStateException("Could not arm reload failure probe", exception);
        }

        ResourceManagerHelper.get(PackType.SERVER_DATA).registerReloadListener(
            new SimpleSynchronousResourceReloadListener() {
                @Override
                public Identifier getFabricId() {
                    return Identifier.fromNamespaceAndPath(
                        "function_compiler_reload_failure_probe",
                        "fail_once"
                    );
                }

                @Override
                public void onResourceManagerReload(ResourceManager manager) {
                    try {
                        if (!Files.deleteIfExists(trigger)) {
                            return;
                        }
                        Path observed = trigger.resolveSibling(trigger.getFileName() + ".observed");
                        Files.writeString(
                            observed,
                            FAILURE_MESSAGE + "\n",
                            StandardOpenOption.CREATE,
                            StandardOpenOption.TRUNCATE_EXISTING
                        );
                    } catch (IOException exception) {
                        throw new IllegalStateException(
                            "Could not signal reload failure probe", exception
                        );
                    }
                    throw new IllegalStateException(FAILURE_MESSAGE);
                }
            }
        );
    }
}
