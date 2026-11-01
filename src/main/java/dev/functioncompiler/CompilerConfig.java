package dev.functioncompiler;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.loader.api.FabricLoader;

import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

public final class CompilerConfig {
    private static final String CONFIG_FILENAME = "function-compiler.json";
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    // Compiler config intentionally separates the generic wrapper/runtime hook
    // surface from each optimizing prototype. enabled remains the shared master
    // switch; each optimization also has its own explicit gate.
    private static boolean enabled = false;
    private static boolean scoreAddEnabled = false;
    private static boolean fusedRegions = false;
    private static boolean selectiveMacros = true;
    private static boolean tieredBytecode = false;
    private static int tieredThreshold = 5;
    private static final Set<String> EXCLUDED_NAMESPACES = new HashSet<>();

    static {
        load();
    }

    private CompilerConfig() {
    }

    public static synchronized void load() {
        try {
            Path configDir = FabricLoader.getInstance().getConfigDir();
            Path configFile = configDir.resolve(CONFIG_FILENAME);
            if (Files.exists(configFile)) {
                try (Reader reader = Files.newBufferedReader(configFile)) {
                    JsonObject json = JsonParser.parseReader(reader).getAsJsonObject();
                    if (json.has("enabled")) {
                        enabled = json.get("enabled").getAsBoolean();
                    }
                    if (json.has("score_add")) {
                        scoreAddEnabled = json.get("score_add").getAsBoolean();
                    } else if (json.has("enabled")) {
                        // Legacy configs only had the bundled master switch.
                        scoreAddEnabled = json.get("enabled").getAsBoolean();
                    }
                    if (json.has("fused_regions")) {
                        fusedRegions = json.get("fused_regions").getAsBoolean();
                    }
                    if (json.has("selective_macros")) {
                        selectiveMacros = json.get("selective_macros").getAsBoolean();
                    }
                    if (json.has("tiered_bytecode")) {
                        tieredBytecode = json.get("tiered_bytecode").getAsBoolean();
                    }
                    if (json.has("tiered_threshold")) {
                        tieredThreshold = json.get("tiered_threshold").getAsInt();
                    }
                    if (json.has("excluded_namespaces")) {
                        EXCLUDED_NAMESPACES.clear();
                        json.getAsJsonArray("excluded_namespaces").forEach(el ->
                                EXCLUDED_NAMESPACES.add(el.getAsString()));
                    }
                }
            } else {
                saveDefault(configFile);
            }
        } catch (Throwable throwable) {
            FunctionCompilerMod.LOGGER.warn("Failed to load config, using defaults: {}",
                    throwable.getMessage());
        }
    }

    private static void saveDefault(Path configFile) {
        try {
            if (configFile.getParent() != null) {
                Files.createDirectories(configFile.getParent());
            }
            JsonObject json = new JsonObject();
            json.addProperty("enabled", false);
            json.addProperty("score_add", false);
            json.addProperty("fused_regions", false);
            json.addProperty("selective_macros", true);
            json.addProperty("tiered_bytecode", false);
            json.addProperty("tiered_threshold", 5);
            json.add("excluded_namespaces", GSON.toJsonTree(Collections.emptyList()));
            try (Writer writer = Files.newBufferedWriter(configFile)) {
                GSON.toJson(json, writer);
            }
        } catch (Exception exception) {
            FunctionCompilerMod.LOGGER.warn("Failed to save default config: {}",
                    exception.getMessage());
        }
    }

    public static boolean isEnabled() {
        return enabled;
    }

    public static boolean isScoreAddEnabled() {
        return enabled && scoreAddEnabled;
    }

    public static boolean isFusedRegions() {
        return fusedRegions;
    }

    public static boolean isSelectiveMacros() {
        return selectiveMacros;
    }

    public static boolean isTieredBytecode() {
        return tieredBytecode;
    }

    public static int getTieredThreshold() {
        return tieredThreshold;
    }

    public static boolean isNamespaceExcluded(String namespace) {
        return EXCLUDED_NAMESPACES.contains(namespace);
    }
}
