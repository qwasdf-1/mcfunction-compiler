package dev.functioncompiler;

/** Standalone Java 25 unit gate for IR-036's uncalibrated structural policy. */
public final class IR036CostModelTest {
    private static int assertions;

    private static void require(boolean test, String message) {
        assertions++;
        if (!test) throw new AssertionError(message);
    }

    private static void selects(
            IR036CostModel.Features features, long calls, boolean allowBytecode,
            IR036CostModel.Backend expected
    ) {
        IR036CostModel.Decision result =
                IR036CostModel.choose(features, calls, allowBytecode);
        require(result.backend() == expected,
                "expected " + expected + " for " + calls + " calls, got " + result);
        require(result.vanillaUnits() > 0 && result.interpreterUnits() > 0
                        && result.bytecodeUnits() > 0,
                "no dimensionless model cost");
    }

    private static void rejects(Runnable action, String label) {
        try {
            action.run();
        } catch (IllegalArgumentException expected) {
            assertions++;
            return;
        }
        throw new AssertionError("failed to reject " + label);
    }

    public static void main(String[] args) {
        var small = new IR036CostModel.Features(2, 0, 0, 0, 1);
        selects(small, 1, true, IR036CostModel.Backend.VANILLA);
        selects(small, 8, true, IR036CostModel.Backend.INTERPRETED);
        selects(small, 256, true, IR036CostModel.Backend.BYTECODE);
        selects(small, 256, false, IR036CostModel.Backend.INTERPRETED);
        // No Bytecode selection if only interpreted IR was explicitly enabled.
        selects(small, 8, false, IR036CostModel.Backend.INTERPRETED);
        // Complex regions retain the exact same legality constraints.
        var guarded = new IR036CostModel.Features(8, 3, 4, 2, 7);
        selects(guarded, 1, true, IR036CostModel.Backend.VANILLA);
        selects(guarded, 1_000, true, IR036CostModel.Backend.BYTECODE);
        // The intended deployment is opt-in and cannot use a negative or
        // unbounded assumed call count that might overflow heuristics.
        rejects(() -> IR036CostModel.choose(small, 0, true), "zero calls");
        rejects(() -> IR036CostModel.choose(small, 1_000_001, true), "too many calls");
        rejects(() -> new IR036CostModel.Features(2, 0, 0, 0, 0),
                "missing observable boundary");
        rejects(() -> new IR036CostModel.Features(65, 0, 0, 0, 64),
                "oversized typed region");
        rejects(() -> new IR036CostModel.Features(2, 3, 0, 0, 1),
                "invalid condition count");
        System.out.println("IR036_JAVA_MODEL_ACCEPTED assertions=" + assertions);
    }
}
