# COMPILER-IR-022 — Original Blastback selector candidate/type/predicate/result investigation

**Status (2026-11-20):** Exact original Minecraft 26.3 selector/type disassembly accepted. Bounded opt-in native four-JVM CONTROL/PLAIN/EMPTY/TIMED measurement and default-off IR-016–019 regression gates in progress. **No selector compiler rewrite, caching, result replacement, causal CPU speedup or verified full Blastback restoration.** Branch work/compiler-coverage, PR #10 draft and unmerged.

## Why IR-022, and exact original source

IR-021's two accepted original Blastback one-TNT CPU studies isolated EntitySelector.findEntities as a reproducible **2.981% and 2.924% inclusive signed sample projection of Server-thread CPU**. Those numbers include necessary game work and are not removable-CPU budgets. To decide whether a future optimizer is justified, IR-022 opens the exact Mojang 26.3 implementation and measures type-filter attempts, delegated combined predicate evaluations and final result handling, not a speculative rewritten selector.

Original SHA-256 publisher Blastback Hotfix 3:

    8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90

Exact original erb:restore/job_tick command at source index 4, validated again before the first native actor is summoned:

    execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] if score @s erb.job = #active erb.job run scoreboard players set #needs_restore erb.tmp 1

## Original Mojang method structure — verified

[Verified original Minecraft 26.3 EntitySelector/ServerLevel/EntityTypeTest method inspection #44840356164](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44840356164) · [mapped method disassembly artifact #14680107345](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44840356164/artifacts/14680107345).

The actual official mapped EntitySelector.findEntities method checks selector permissions, constructs spatial position/AABB and original Predicate through getPredicate, allocates an ObjectArrayList, calls addEntities for the applicable ServerLevels, and calls sortAndLimit on the results.

EntitySelector.addEntities delegates to one of two original ServerLevel.getEntities overloads, one for AABB and one for unbounded queries, passing **both** EntityTypeTest (normally the type=minecraft:marker filter) and the combined Predicate. EntityTypeTest exposes getBaseClass and tryCast; the server's entity storage can use getBaseClass for an initial indexed class filter. This means counting tryCast callbacks alone **does not count all raw world entities considered or all objects rejected by type**. The predicate constructed by getPredicate can include context-free tag rules, enabled-feature, AABB and/or range predicates. Its single Boolean return cannot by itself separate the tag=erb.block test from tag=!erb.verified or other context-dependent checks. The first-pass observer expressly does NOT claim to recover those individual reasons.

sortAndLimit applies the original ordering function when there are multiple candidates and returns a subList bounded by the original maxResults. The datapack's @e query does not justify assuming a special no-sort/no-limit path across other selectors.

## New bounded native diagnostic, not a selector implementation

CompilerSelector022Probe and CompilerSelector022Mixin observe six original method boundaries in the *actual original command's* BuildContexts scope. No command is reparsed, child function is inlined, callback is bypassed or original ServerLevel#getEntities call is changed.

| Instrumented native synchronous stage | Stream | Sample stride | Observation |
| --- | --- | ---: | --- |
| EntitySelector.findEntities | selector_find_entire | 1/16 | Total outer selector and final returned sources |
| EntitySelector.getPredicate | selector_build_predicate | 1/16 | Inclusive construction of original composite Predicate |
| EntitySelector.addEntities | selector_gather_entities | 1/16 | Native ServerLevel type/query/filter and appended results |
| Original EntityTypeTest.tryCast | native_type_try_cast | 1/256 | Type tests and nonnull typed results actually performed inside query |
| Original composite Predicate.test | native_composite_predicate | 1/128 | Calls and true results for *combined* native predicate |
| EntitySelector.sortAndLimit | selector_sort_and_limit | 1/16 | Original presort source count and final retained count |

The new type and predicate count/timing hooks **forward the original native tryCast/test exactly once** and never alter the input entity, return value, exceptions or output list. They are inserted as temporary proxies around the arguments to ServerLevel.getEntities for this exact command when the diagnostic is on. This changes callback object identity and adds per-candidate allocations/atomic counters; it is not literally zero-overhead or an unmodified execution path for measurement. Any measured CPU projection **includes diagnostic probe effects** and is not evidence of a production speedup. The native CONTROL arm deliberately does not wrap either object; it records the outer original selector, predicate-build/gather/sort, world/actor and Linux Server-thread CPU as a separate real-workload reference.

The research flags require both FC_CPU022_NAMESPACE=erb and FC_CPU022_MODE=control|plain|empty|timed at process start, plus an explicit bounded functioncompiler cpu022-start / cpu022-stop command. All flags are OFF in regular builds. Under the mode gate:

- CONTROL uses original EntityTypeTest and Predicate object identities and samples **no** Java CPU clocks. It counts only native outer stages.
- PLAIN delegates the original type and predicate methods through counting proxies without CPU clocks.
- EMPTY samples two immediately adjacent ThreadMXBean current-thread CPU reads at the predetermined native method ordinals.
- TIMED brackets the same original native method at identical per-stream strides, using the original callback and result. A separate /proc Server-thread schedstat CPU clock is recorded as an independent denominator. All sampled intervals must be nonnegative and there must be exactly floor(visits/stride) valid samples.

All four modes use fresh Java25/Minecraft26.3 JVMs, the original byte-pinned Blastback ZIP, the established 30-second real one-TNT capture/restore fixture, strict pre-event world/template comparison and tagged TNT observed before timing. Invalid actor or world probes are rejected before the event, never silently counted as a successful CPU sample. Each accepted arm must show genuine selector activity and the expected original returned/gathered/sorted result-cardinality conservation. The four worlds are **not** identical-work causal A/A+A/B treatments; no clock-sampled fraction is a removable-work bound or tested optimization.

## Native acceptance gates

1. Original mapped-bytecode references match exact selector, type and ServerLevel method descriptors.
2. Java25/Fabric native project compiles, all IR-022 safety tests pass and the original publisher ZIP/source line matches its SHA/index.
3. Four original server JVMs successfully run their bounded event, with consistent outer source visits, unwrapped CONTROL identity, exact native filter pass-through, strictly valid clock rows and published per-candidate counts.
4. Separately repeat the original four modes to gauge whether filtered-candidate ratios and CPU stage projections are stable. Preserve signed corrections, including negative or below-empty-clock effects, without inventing speedups.
5. Post-observer default-off IR-016–019 native semantic regressions must match original vanilla states, quotas, entity sources, command callback/fallback/child-call behavior.
6. Archive research workflows as manual-only and retain draft/unmerged PR #10, production flags OFF.

If a stage proves cheap, mandatory or dominated by probe overhead, record that fact and do **not** implement a replacement. A future optimization would require a specific native semantics-preserving mechanism (e.g. carefully justified selector predicate reuse) and an *unwrapped*, unbiased or placebo-controlled CPU A/B study, including entity/tag mutation, sorting/limit, permissions, error, quota, frame and reentrancy parity.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir022_cpu.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir022_cpu.py

**All numerical candidate ratios and CPU fractions require accepted native results; no numbers are projected from IR-021.**
