# COMPILER-IR-020 — Original Blastback selector-fork CPU cost screen

**Status (2026-11-20):** **ACCEPTED two independent three-JVM native original Blastback calibrated CPU-clock matrices**, with exact publisher source, pre-event world, clock/host quality and source-exposure gates passed in all six arms; default-off IR-016–019 native semantic regressions accepted. The only measured new capability is an opt-in research CPU diagnostic. **No compiled selector/dispatch opcode, causal speedup, complete Blastback restoration or production promotion.** Research branch work/compiler-coverage, draft PR #10 unmerged.

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

This is a bounded, sampled descriptive cost screen. One independently timed JVM does not provide a confidence interval, and deterministic 1/16 or 1/128 sampling may correlate with changing source/entity work through the 30-second window. An additional, independently started original three-JVM matrix has now passed and is documented below, but two sparse-clock replications still do not constitute a randomized causal CPU experiment.

## Accepted independent native clock replication

[Independent repeat of original Minecraft 26.3 six-command? no: three-JVM PLAIN / EMPTY / TIMED study #44834904332](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834904332) · [full second event/clock samples and original fixture observations #14677158595](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44834904332/artifacts/14677158595).

The same unchanged original Blastback publisher, byte-pinned original command, 30-second direct native TNT event, unchanged three method boundaries, sparse clock strides and bounded pre-event source/template integrity checks ran again on **three additional independently booted JVMs**. Every method had zero invalid/missing samples and all independent host-quality gates passed.

| Original 30-second native observation | PLAIN | EMPTY | TIMED |
| --- | ---: | ---: | ---: |
| Minecraft ticks | 600 | 601 | 619 |
| Original selector source builds | 1,243 | 1,243 | 1,248 |
| Native per-fork execute and scoreboard callback entries each | 320,465 | 321,596 | 328,008 |
| Linux Server-thread CPU | 8.613 s | 8.322 s | 8.641 s |

The repeat EMPTY sampled 77 Build / 2,512 Execute / 2,512 Leaf original calls; TIMED sampled 78 Build / 2,562 Execute / 2,562 Leaf calls at the exact predeclared ordinals.

| Synchronous method span | Repeat EMPTY clock mean | Repeat TIMED method mean | Repeat signed corrected per call | Repeat projected share of TIMED Server CPU |
| --- | ---: | ---: | ---: | ---: |
| restore_selector_build | 1,332.26 ns | 392,471.97 ns | **391,139.71 ns** | **488.14 ms / 5.649%** |
| restore_terminal_execute | 580.04 ns | 1,620.29 ns | **1,040.25 ns** | **341.21 ms / 3.949%** |
| restore_scoreboard_leaf (nested) | 255.35 ns | 405.68 ns | **150.34 ns** | **49.31 ms / 0.571%** |

### Across the two completely independent original three-arm studies

| Original inclusive method | First TIMED CPU projection | Independent repeat |
| --- | ---: | ---: |
| Source/selector fork BuildContexts stage | **5.631%** | **5.649%** |
| Original per-entity ExecuteCommand stage | 3.533% | 3.949% |
| Nested original scoreboard callback | 0.412% | 0.571% |

The first and second *selector/context-building* projections differ by only 0.018 percentage points under these fixed fixture conditions, a reproducible descriptive workload lead. This agreement is NOT a statistical confidence interval or proof that those 5.6% could be removed. The per-fork execute/leaf values vary more. In both studies the scoreboard callback's signed correction of only 106–150 ns remains **below the independent EMPTY clock-read mean of 255–285 ns**, so it is particularly unsuitable for extrapolation into a purported large optimizer benefit.

**Decision:** No IR-020 selector or function-dispatch optimization is promoted. The next technically plausible question is whether the **required** context-fork setup can be represented more efficiently while preserving every per-entity source, conditional score comparison, callback, failure, result, command quota and queued frame. It must be separately tested against the genuine original-world work and measured as a causal uninstrumented performance treatment before any speedup claim. We have not measured what share of the inclusive 5.6% is *actually removable*.

## Decision boundary

IR-020 is an attribution experiment, not authorization to optimize 317k real per-entity commands. The key decision is whether substantial measured cost belongs to avoidable dispatcher/selector machinery rather than necessary entity lookup, score comparison, callback delivery and scoreboard mutation. Only after a stable cost estimate and native fork/return/error/trace/quota parity should a future, separately gated selector-aware compiler operation be proposed. Previous IR-019 static source coverage alone does not justify one.

Do not merge default-off research Mixins into production without a separately tested disabled-hook overhead study. The full-restoration Blastback oracle remains unresolved; no CPU speedup, full restoration, or general selector rewrite is claimed.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir020_cpu.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir020_cpu.py
