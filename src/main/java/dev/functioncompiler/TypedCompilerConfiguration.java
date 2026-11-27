package dev.functioncompiler;

import java.util.Set;

/** Startup-only opt-in profile. Explicit per-feature flags retain precedence. */
public final class TypedCompilerConfiguration {
    private static final String PROFILE = System.getenv("FC_TYPED_COMPILER_PROFILE");
    private static final String NAMESPACE = System.getenv("FC_TYPED_IR_NAMESPACE");
    private static final boolean VALIDATED = "validated".equals(PROFILE)
            && NAMESPACE != null && !NAMESPACE.isBlank();
    private static final Set<String> VALIDATED_FLAGS = Set.of(
            "FC_TYPED_IR_RANGE_GUARDS", "FC_TYPED_IR_SELF_HOLDER",
            "FC_TYPED_IR_EXTENDED_SCORE", "FC_TYPED_IR_COMPOUND_SCORE",
            "FC_TYPED_IR_DATAFLOW", "FC_TYPED_IR_ARITHMETIC",
            "FC_TYPED_IR_REENTRANT_SAFE", "FC_TYPED_IR_DISPATCH",
            "FC_TYPED_IR_GUARD_TERMINAL", "FC_TYPED_IR_NATIVE_STORE",
            "FC_TYPED_IR_GUARD_RUN_REUSE", "FC_TYPED_IR_GUARD_PREFLIGHT_REUSE");
    private TypedCompilerConfiguration() {}
    public static boolean profileActive() { return VALIDATED; }
    public static String mode() {
        String mode = System.getenv("FC_TYPED_IR_MODE");
        return mode == null ? (VALIDATED ? "bytecode" : "") : mode;
    }
    public static boolean flag(String name) {
        String explicit = System.getenv(name);
        return explicit != null ? Boolean.parseBoolean(explicit)
                : VALIDATED && VALIDATED_FLAGS.contains(name);
    }
    public static String summary() {
        return " typed_profile=" + (VALIDATED ? "validated" : "off")
                + " typed_mode=" + mode()
                + " typed_namespace=" + (NAMESPACE == null ? "" : NAMESPACE)
                + " typed_reentrant_safe=" + flag("FC_TYPED_IR_REENTRANT_SAFE")
                + " typed_guard_reuse=" + flag("FC_TYPED_IR_GUARD_RUN_REUSE")
                + " typed_preflight_reuse=" + flag("FC_TYPED_IR_GUARD_PREFLIGHT_REUSE")
                + " fixture_build=" + CompilerFixtures.ENABLED;
    }
}
