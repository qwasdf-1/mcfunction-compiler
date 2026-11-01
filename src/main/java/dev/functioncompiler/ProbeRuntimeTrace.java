package dev.functioncompiler;

public final class ProbeRuntimeTrace {
    private static volatile String activeLabel = "idle";

    private ProbeRuntimeTrace() {
    }

    public static boolean enabled() {
        return ProbeConfiguration.traceEnabled() && !"idle".equals(activeLabel);
    }

    public static String label() {
        return activeLabel;
    }

    public static void begin(String label) {
        activeLabel = label;
    }

    public static void end() {
        activeLabel = "idle";
    }
}
