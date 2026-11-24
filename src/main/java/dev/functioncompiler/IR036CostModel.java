package dev.functioncompiler;

import java.util.Objects;

/**
 * IR-036: opt-in structural code-generation cost policy, free of Minecraft
 * dependencies so its decisions can be tested without launching a server.
 *
 * IMPORTANT: these are DIMENSIONLESS heuristic work units, not profiled CPU
 * nanoseconds, measured instructions, or a calibrated speedup prediction.
 * The policy only estimates how much compilation setup might be amortized by
 * an explicitly assumed call count. It is disabled by default, and cannot
 * authorize cross-command effect elimination.
 */
final class IR036CostModel {
    private IR036CostModel() {}

    enum Backend { VANILLA, INTERPRETED, BYTECODE }

    record Features(
            int instructions, int conditionals, int binaries,
            int dynamicHolders, int blockedBoundaries
    ) {
        Features {
            if (instructions < 2 || instructions > 64
                    || conditionals < 0 || binaries < 0 || dynamicHolders < 0
                    || blockedBoundaries != instructions - 1
                    || conditionals > instructions || binaries > instructions
                    || dynamicHolders > instructions) {
                throw new IllegalArgumentException("invalid typed effect/cost features");
            }
        }
    }

    record Decision(
            Backend backend, long vanillaUnits, long interpreterUnits,
            long bytecodeUnits, long assumedInvocations
    ) {
        Decision {
            Objects.requireNonNull(backend);
            if (vanillaUnits <= 0 || interpreterUnits <= 0
                    || bytecodeUnits <= 0 || assumedInvocations <= 0) {
                throw new IllegalArgumentException("invalid heuristic estimate");
            }
        }
    }

    static Decision choose(Features f, long expectedCalls, boolean allowBytecode) {
        Objects.requireNonNull(f);
        // A bounded, explicit caller assumption; no inferred runtime hotness.
        if (expectedCalls < 1 || expectedCalls > 1_000_000) {
            throw new IllegalArgumentException("expected calls must be in [1,1000000]");
        }
        long n = f.instructions();
        long g = f.conditionals();
        long b = f.binaries();
        long d = f.dynamicHolders();

        // All three backends perform the same per-command scoreboard effects.
        // These weights are *heuristics* and deliberately expose that fact.
        long common = 4 * g + 3 * b + 2 * d;
        long vanilla = (12 * n + common) * expectedCalls;
        long interpreted = 24 + 3 * n + 4 * g
                + (7 * n + common + 3) * expectedCalls;
        long bytecode = 200 + 18 * n + 14 * g + 5 * b
                + (3 * n + common + 3) * expectedCalls;

        // Ties deliberately keep the less intrusive backend. Never use the
        // model to bypass the original callback/queue/feedback boundaries.
        Backend selected = Backend.VANILLA;
        long best = vanilla;
        if (interpreted < best) {
            selected = Backend.INTERPRETED;
            best = interpreted;
        }
        if (allowBytecode && bytecode < best) {
            selected = Backend.BYTECODE;
        }
        return new Decision(selected, vanilla, interpreted, bytecode, expectedCalls);
    }
}
