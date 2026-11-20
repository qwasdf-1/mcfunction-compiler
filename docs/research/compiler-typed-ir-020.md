# COMPILER-IR-020 — Original Blastback selector-fork CPU cost screen

**Status (2026-11-20):** Native research-only CPU measurement in progress. The original publisher command, Java25/Minecraft26.3 build, plain native execution boundary and post-change IR-016–019 semantic regressions have passed. All CPU attribution requires the complete independent PLAIN/EMPTY/TIMED matrix. No compiled selector or conditional function dispatch opcode, no performance claim, no complete restoration or production promotion. Branch work/compiler-coverage, open draft PR #10.

## Original source and observable hypothesis

In the accepted IR-019 one-TNT event, an original source command in erb:restore/job_tick at source index 4 was reached about 1,242 times but entered its original terminal callback about 319,509 times. The original publisher Blastback Hotfix 3 archive is pinned byte-for-byte to SHA-256 8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90. Its exact unmodified command at source index 4 is:

    execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] if score @s erb.job = #active erb.job run scoreboard players set #needs_restore erb.tmp 1

The new CI explicitly verifies that this original command appears exactly once at source index 4 before timing. This is a multi-stage entity-context FORK and scoreboard predicate, not an exact single-guard/static-function dispatch candidate. The CPU study should NOT conflate its source-entry count, per-entity terminal callbacks, successful predicates, or mutations.

## Exact native CPU boundaries

CompilerRestoreCpuProbe adds three opt-in streams to existing research Mixin surfaces for BuildContexts and ExecuteCommand, plus one wrapper around the genuine original parsed ScoreboardCommand terminal callback. It retains the original Command.run result, exception, live execution source, queue, frame, quota, and scoreboard behavior. The feature activates only when FC_CPU020_NAMESPACE=erb and FC_CPU020_MODE=plain|empty|timed, plus explicit functioncompiler cpu020-start and cpu020-stop event-window commands. The feature does not create any new parser, selector implementation, scheduler shortcut or compiled instruction.

| Stream | Measured original method | Sample stride | Distinction |
| --- | --- | ---: | --- |
| restore_selector_build | BuildContexts.execute | 1/16 | Source/context and fork setup. Later queued work may occur outside this call. |
| restore_terminal_execute | ExecuteCommand.execute | 1/128 | Original per-fork command execution, includes terminal callback and results. |
| restore_scoreboard_leaf | ScoreboardCommand Command.run | 1/128 | Real original callback, nested inside the ExecuteCommand stream. |

These are NOT a disjoint breakdown. Never add the terminal execute and nested leaf projections, never label the total as avoidable compiler overhead, and do not equate callback entries to successful scoreboard changes.

## Frozen native experiment

Three fresh Minecraft 26.3/Java25 Fabric server JVMs run the exact original publisher pack, the same directly summoned tagged 160-tick-fuse TNT actor, the five independently checked original palette witness blocks, the cloned source/template region, forced chunks and 30 seconds of real Blastback capture/restoration. The native source/template equality is a strict PRE-event requirement; at most three logged setup-only clone preparations are permitted. No post-event timing data are dropped and no event is repeated selectively.

PLAIN observes call counts without touching the Java CPU clock. EMPTY records two adjacent ThreadMXBean current-thread CPU reads on the frozen sample ordinals and delegates to the same native method. TIMED brackets the original method at the same sampling stride. An independent Linux /proc Server-thread schedstat running-nanosecond clock supplies the inclusive whole-window CPU denominator, with runqueue delay and cgroup throttling diagnostics. Sample gates require zero invalid intervals, exactly floor(visits/stride) samples for each active stream, at least 24 build samples, at least 128 execute and leaf samples, nonempty original gameplay work, and no more than a 1.5× spread in exposure among the three independent arms. Samples that fail a gate are reported invalid, not treated as zero CPU.

The reported signed correction per method is mean TIMED inclusive CPU minus mean EMPTY clock-only CPU, multiplied by TIMED observed calls for a descriptive inclusive projection. The method spans include meaningful original game work, and the correction does not measure the counterfactual CPU saving from removing that work. Different boots and differing actor populations are not equal-denominator randomized causal A/B trials; a negative correction must remain negative.

## Accepted unaffected native behavior

[Post-hook regression run #44834124078](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834124078) passed all previous accepted original Minecraft semantics with IR-020 clocks disabled: IR-016 mixed original call barriers 126/126 full states per mode, IR-017 ranged score guards 168/168, IR-018 entity source and native barriers 87/87, and IR-019 conditional original function dispatch 84/84. All suites built on Java 25, all original scoreboards/command quotas matched the vanilla arms. This proves bounded semantic preservation, NOT zero CPU overhead from the installed-but-disabled research Mixins.

[IR-016 native artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834124078/artifacts/14677553901) · [IR-017 artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834124078/artifacts/14677903542) · [IR-018 artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834124078/artifacts/14676892844) · [IR-019 artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834124078/artifacts/14676538006).

## Original native CPU result

The first native PLAIN arm has independently accepted 1,241 original BuildContexts source visits, 317,551 ExecuteCommand calls and 317,551 original ordinary scoreboard callbacks, 589 ticks and 7.0008 seconds of Linux Server-thread CPU. The following EMPTY-mode fixture initially rejected a mismatch between source and cloned world before the clock window; that failed setup is not a valid performance observation. A bounded pre-event fixture stabilization correction is being tested. Complete clock-corrected CPU results must be added here only after the remaining independent native arms pass.

## Decision boundary

IR-020 is an attribution experiment, not authorization to optimize 317k real per-entity commands. The key decision is whether substantial measured cost belongs to avoidable dispatcher/selector machinery rather than necessary entity lookup, score comparison, callback delivery and scoreboard mutation. Only after a stable cost estimate and native fork/return/error/trace/quota parity should a future, separately gated selector-aware compiler operation be proposed. Previous IR-019 static source coverage alone does not justify one.

Do not merge default-off research Mixins into production without a separately tested disabled-hook overhead study. The full-restoration Blastback oracle remains unresolved; no CPU speedup, full restoration, or general selector rewrite is claimed.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir020_cpu.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir020_cpu.py
