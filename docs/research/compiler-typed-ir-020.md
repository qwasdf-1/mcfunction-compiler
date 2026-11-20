# COMPILER-IR-020 — Original Blastback selector-fork CPU cost screen

**Status (2026-11-20):** **ACCEPTED first three-JVM descriptive original Blastback CPU-clock matrix**, all native sample and original-source/world gates passed; a second independently booted three-arm replication is being run to check clock variability. Default-off original IR-016–019 native semantic regressions accepted. **No compiled selector/dispatch opcode, CPU speedup, full restoration or production promotion.** Work remains on work/compiler-coverage, draft PR #10.

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

## Accepted first original native three-JVM CPU screen

[Accepted original PLAIN / EMPTY / TIMED workflow #44834332331](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834332331) · [all raw clocks, source/template checks, 30-second event state and Linux Server-thread CPU #14676503441](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834332331/artifacts/14676503441).

An initial trial accepted its PLAIN arm but stopped **before** the EMPTY clock window on a clone/template mismatch despite all five original witness blocks matching. That invalid pre-event preparation was not admitted as a CPU observation. The subsequent full trial explicitly repeated pre-event clone preparation at most three times, with every subsequent world/clock/event gate enforced. All three independently started Minecraft 26.3/Java25 server modes passed.

| Native observed quantity | PLAIN | EMPTY | TIMED |
| --- | ---: | ---: | ---: |
| Game ticks in 30-second capture/restoration window | 601 | 624 | 601 |
| Original exact source BuildContexts visits | 1,238 | 1,242 | 1,250 |
| Original per-entity ExecuteCommand entries | 315,428 | 320,897 | 323,827 |
| Original terminal ScoreboardCommand callbacks | 315,428 | 320,897 | 323,827 |
| Server-thread Linux running CPU | 7.480 s | 8.292 s | 8.377 s |
| Host-quality gate and original actor/fixture | Pass | Pass | Pass |

The execution count ratio reflects roughly 255–259 terminal callbacks per source entry, but this is NOT the number of matching score conditions or changed scoreboard values. PLAIN performed **zero** CPU-clock sampling. EMPTY sampled **77 Build** and **2,507 Execute/Leaf** calls; TIMED sampled **78 Build** and **2,529 Execute/Leaf** calls, with exactly floor(visits/stride) observations, zero dropped or invalid intervals, and verified original unmodified source text. All three modes finished their 30-second observation without asserting completed world restoration.

### Calibrated, signed original method-cost observations

| Original synchronous method span | EMPTY clock mean | TIMED inclusive mean | Signed corrected ns/call | Descriptive TIMED Server CPU fraction |
| --- | ---: | ---: | ---: | ---: |
| restore_selector_build | **1,334.64 ns** | **378,704.60 ns** | **377,369.97 ns** | **471.71 ms; 5.631%** |
| restore_terminal_execute | **577.51 ns** | **1,491.48 ns** | **913.97 ns** | **295.97 ms; 3.533%** |
| restore_scoreboard_leaf (nested in execute) | **284.99 ns** | **391.48 ns** | **106.49 ns** | **34.48 ms; 0.412%** |

The original selector/context-building stage is substantially more expensive per source entry than a single scoreboard callback. The **leaf correction (106 ns) is smaller than EMPTY's mean clock-only interval (285 ns)** and cannot support a precise positive CPU claim. The execute/leaf method-cost measurements overlap; their descriptive CPU percentages are **not additive**. Even a hypothetical combined build + terminal-execute inclusive cost is not proof of removable compiler-owned work, because it contains required entity selection, per-entity score lookup and actual scoreboard result processing. The work and marker population differ across independent boots; the whole-Server CPU figures are **not** causal treatment effects and should not be interpreted as an improvement or slowdown.

This is a bounded, sampled descriptive cost screen. One independently timed JVM does not provide a confidence interval, and deterministic 1/16 or 1/128 sampling may correlate with changing source/entity work through the 30-second window. A second independent original three-JVM matrix is being run before treating these proportions as stable across repeated experiments.

## Decision boundary

IR-020 is an attribution experiment, not authorization to optimize 317k real per-entity commands. The key decision is whether substantial measured cost belongs to avoidable dispatcher/selector machinery rather than necessary entity lookup, score comparison, callback delivery and scoreboard mutation. Only after a stable cost estimate and native fork/return/error/trace/quota parity should a future, separately gated selector-aware compiler operation be proposed. Previous IR-019 static source coverage alone does not justify one.

Do not merge default-off research Mixins into production without a separately tested disabled-hook overhead study. The full-restoration Blastback oracle remains unresolved; no CPU speedup, full restoration, or general selector rewrite is claimed.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir020_cpu.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir020_cpu.py
