package dev.functioncompiler;

/**
 * IR-010: version oracle for explicitly watched scoreboard slots.
 *
 * Implemented only on the server Scoreboard by a research-only Mixin. No
 * public ScoreAccess implementation is replaced. Each watched slot gets a
 * monotonic revision on value change or removal. A read is reusable only
 * while the revision AND current Objective object identity both match.
 */
public interface ScoreValueRevisionAccess {
    record Key(String holder, String objective) {}

    /** Register a slot on first read and return its current revision. */
    long functionCompiler$watch(Key slot);
}
