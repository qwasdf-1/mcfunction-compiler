# COMPILER-IR-022 — Original Blastback selector candidate/type/predicate/result investigation

**Status (2026-11-20):** ACCEPTED research-only IR-022: exact mapped 26.3 method signatures, two independent four-JVM CONTROL/PLAIN/EMPTY/TIMED original Blastback studies (eight JVMs), and post-hook IR-016–019 native semantic regressions. The initial overbroad selector census was explicitly invalidated and corrected. No compiled selector, tag index, cache, optimized scheduler, causal CPU speedup, complete restored-world correctness or production promotion. Branch work/compiler-coverage; draft PR #10 unmerged; production OFF.

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

## Invalid pilot and corrected exact selector attribution

[Rejected initial native pilot #44840974441](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44840974441) was rejected by its own conservation checks. The original broad BuildContexts scope included hundreds of thousands of unrelated current-entity @s lookups in the downstream score modifier as if they were the original execute-as world scan. These @s lookups take an early-return path and never use the native addEntities/sortAndLimit pipeline, so the outer selector numbers were INVALID and are not cited as CPU evidence.

The fix scopes findEntities to the **parsed Brigadier execute-as modifier** inside the exact original command. Downstream score-modifier @s queries are expressly excluded, as are nested unrelated selectors. All subsequent accepted modes enforce exact equality of original world-query gathered entities, final sortAndLimit retained entities and actual selector return counts, and of combined predicate true results to native collected entities.

## Two accepted four-JVM original publisher experiments

[First corrected native CONTROL/PLAIN/EMPTY/TIMED matrix #44841656643](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841656643) · [raw original-world and clock evidence #14681506985](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841656643/artifacts/14681506985).

[Independently booted four-JVM original publisher replication #44841711929](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841711929) · [raw native repeated evidence #14680294665](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841711929/artifacts/14680294665).

Both original Hotfix 3 ZIP SHA pins, exact function source index, real tagged TNT (observed before clocks start), pre-event template/witness checks, fixed 30-second window, sample-integrity rules and Linux Server-thread host quality passed. The separate CONTROL mode retained original native type/predicate object identities and read no Java CPU clock, selecting **312,157** and **325,711** original entities respectively; the other modes delegated the exact native type tests and composite predicates once each. The independently booted original worlds need not process identical game ticks or entity histories.

| Direct native original selector observation | First PLAIN JVM | Independent PLAIN JVM |
| --- | ---: | ---: |
| Target execute-as marker selector queries | 1,242 | 1,245 |
| EntityTypeTest.tryCast calls reached | **4,125,924** | **4,134,645** |
| Native type-test nonnull returns | **4,075,002** | **4,084,845** |
| Native type-test null results | 50,922 | 49,800 |
| Native combined Predicate.test calls | **4,075,002** | **4,084,845** |
| Combined predicate true results | **326,192** | **320,284** |
| Combined predicate false results | **3,748,810** | **3,764,561** |
| World-query gathered and final sorted entities | **326,192** | **320,284** |
| Type-test success fraction of reached tryCast calls | **98.77%** | **98.80%** |
| Combined predicate success fraction of reached typed candidates | **8.00%** | **7.84%** |

**Reproducible finding:** About **92% of type-qualified candidates were rejected by the native combined predicate** under these genuine original Blastback event windows. This is the main *candidate rejection gate*, not automatically the main avoidable CPU operation. The original entity-storage index can prefilter by getBaseClass before tryCast; none of these counts include unseen raw entities filtered out before that call. The combined predicate may include both original tags, enabled-feature and spatial restrictions; individual tag rejection counts are NOT directly observed and must not be invented.

### Native CPU cost screen and its limits

All PLAIN calls avoided CPU clocks. EMPTY observed adjacent current-thread CPU clocks; TIMED bracketed the original delegated method on fixed sampling strides, with independent Linux Server-thread running-CPU denominators. All required samples were present and nonnegative. Signed TIMED-minus-EMPTY corrections were **not** clamped to positive values.

| Inclusive stage projection of TIMED Server-thread CPU | First matrix | Independent repeat |
| --- | ---: | ---: |
| Entire original EntitySelector.findEntities | 4.345% | 4.820% |
| Nested original addEntities / world-query stage | 5.640% | 4.833% |
| Original composite Predicate.test with diagnostic proxy | 2.493% | 2.413% |
| Original EntityTypeTest.tryCast with diagnostic proxy | **−0.725%** | **+0.507%** |
| Original getPredicate construction | 0.0074% | 0.0118% |
| Original sortAndLimit result handling | 0.0071% | 0.0123% |

This is **NOT an exact CPU partition and NOT a speedup estimate**. In the first matrix the independently sampled **nested addEntities projected fraction EXCEEDS its enclosing findEntities fraction** (5.640% vs 4.345%). That physical inconsistency is a clear warning about differing fixed sampling phases, workload diversity and wrapper overhead; we retain the raw evidence instead of forcing an exclusive partition. The second projection is nearly equal between nested and enclosing spans, not evidence that result construction is free.

The combined native predicate signed correction was **49.26 ns/test** and **46.82 ns/test**, each smaller than the respective EMPTY clock-only mean of **782.41 ns** and **277.82 ns**. The type-test correction changed sign, **−14.15 ns/test** versus **+9.72 ns/test**. Predicate and type proxy allocation and atomic counters are part of TIMED and EMPTY observations but absent from the unwrapped CONTROL. Consequently **neither per-candidate CPU saving nor a precise exclusive cost is established**, and the apparent whole-window CPU fraction of the composite predicate cannot be taken as avoidable or a treatment result. Sorting and predicate construction have very small projected whole-Server CPU shares, but are likewise only diagnostic inclusive method samples.

## Post-installation native behavior and next gate

[Accepted IR-022 default-off semantic regression #44841661882](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841661882): four separate Minecraft 26.3 Java25 differential suites all passed, **IR-016 126/126**, **IR-017 168/168**, **IR-018 87/87**, **IR-019 84/84** complete vanilla scoreboard states per mode. This is bounded native command/frame/quota/callback behavior when the new observer is disabled, NOT proof of zero disabled-hook overhead.

[IR-016 artifact #14680263657](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841661882/artifacts/14680263657) · [IR-017 artifact #14681601338](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841661882/artifacts/14681601338) · [IR-018 artifact #14681282070](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841661882/artifacts/14681282070) · [IR-019 artifact #14680808438](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44841661882/artifacts/14680808438).

**Decision:** IR-022 is ACCEPTED as measured original selector candidate filtering with diagnostic-only CPU observations; no selector compiler, tag index or cached predicate result is implemented. A plausible next investigation is **mutation frequency and correct invalidation cost of tag-filter membership**. Before any tag-index or reused-result experiment, establish native visibility under tag updates, removal/spawn/dimension/reload changes, permissions, sorting/limit, partial quotas, callback and reentrant queue behavior. Then compare an actual opt-in replacement using **uninstrumented, placebo-controlled native A/A+A/B CPU runs**, never using the current proxy-timing result as a claimed speedup or removable-work budget.

## Native acceptance gates — all satisfied

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

All figures above are directly from accepted original native four-JVM runs #44841656643 and #44841711929. No optimizer or causal CPU speedup was tested.
