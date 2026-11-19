# COMPILER-MACRO-006 — unique-index macro instantiation CPU screen

**Status:** Preregistered, **diagnostic only**. A new compiler-owned candidate on the existing `work/compiler-coverage` branch and draft PR #10, after the stopped positioned-call/queue predicate CPU004–005 hypotheses. No new Mixin or production optimizer was added. The study keeps the **shipped selective macro-argument fast path enabled**, but adds an exact-function, opt-in **diagnostic wrapper** for `load_next`. It is **not** an untouched-production performance measurement and is not an artificial synthetic workload.

## Distinct source/evidence-based hypothesis

The accepted [COMPILER-ACCEPTANCE-002](compiler-runtime-acceptance-002.md) raw native study found, in **both** its score-add and selective-macro arms:

- `vm:queue/load_next`: **1,952 `macro_new_expansion`**, **0 parameter-cache hits**;
- its two expanded command shapes are `data modify entity @s data.cursor set from entity @s data.frontier[INDEX]` and `execute unless data entity @s data.frontier[INDEX] run return run function vm:operation/complete`;
- in the score-add diagnostic, each of the 1,952 indexed NBT-copy commands was declined as a `bare_declined` executable and each return/function command was `chain_executable_declined`; these **are not CPU counts**;
- in contrast, `vm:queue/enqueue_match` recorded one expansion with 5,615 parameter-cache hits and the later CPU005 measured its synchronous conditional predicate work at only ~0.096% of event CPU. Do not revisit that negative hypothesis.

**Candidate:** A compiler specialization for a parameterized NBT-list-index macro might avoid repeatedly parsing two structurally identical command trees whose list index changes on each queue head. The *hypothesis* is compiler-controlled instantiation, not eliminating needed NBT copying, queue advancement or result/return callbacks. **No implementation is authorized until a material CPU fraction is measured.**

The runner SHA-verifies the unmodified **original publisher Vein Miner 5.3.0+26.3 ZIP** (`fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`), reads `data/vm/function/queue/load_next.mcfunction`, asserts precisely two indexed-macro source commands using the **same single substitution variable**, and prints their full source. If that source contract fails, no CPU observation is accepted.

## Exact synchronous CPU-clock streams

Existing `ProbeFunctionWrapper.instantiate` is the only timed method. The existing `FunctionBuilderMixin` must explicitly opt in `vm:queue/load_next` for this diagnostic (without changing other macros); production selective-macro mode does not normally wrap every macro function. An explicitly enabled, exact-function opt-in `FC_MACRO006_NAMESPACE=vm` plus `FC_MACRO006_MODE=plain|empty|timed` is required; `function_compiler_probe macro006-start/stop` wraps **only the genuine native mining event**. No broad Java scheduler, command-execution or entity-NBT Mixins are added.

| Stream | Exact original synchronous method region | Expected calls / native event |
| --- | --- | ---: |
| `macro_total` | Full `ProbeFunctionWrapper.instantiate` call for `vm:queue/load_next`, including cache lookup and original macro expansion | 1,952 |
| `argument_extraction` | Existing `MacroTemplateCompiler.extractArguments` only | 1,952 |
| `vanilla_macro_instantiation` | Original `delegate.instantiate(arguments, dispatcher)` for a cache miss, including vanilla template substitution, Brigadier parse and function materialization | 1,952 |

The three spans **overlap**: the total includes the two child spans. `vanilla_macro_instantiation` is a larger span than pure parse overhead; not all of it is necessarily removable. The probe also records `cache_hits` and `extraction_null`, expected both **zero**; deviations invalidate the pinned workload hypothesis. All ordinary callbacks, state changes and function semantics execute unmodified, including exceptions and return/callback behavior.

PLAIN performs counters only, EMPTY reads two adjacent `ThreadMXBean.getCurrentThreadCpuTime` values before delegation at every 8th call, TIMED brackets the original synchronous operation at the matching ordinal. No CPU clock reads outside an active event, and no Spark, JFR, CPU004–005, compiler-acceptance or execution-census counters may be enabled.

## Frozen native protocol and acceptance

Three fresh independent JVMs, fixed order **PLAIN → EMPTY → TIMED**, Minecraft 26.3 Fabric, Java 25, `--compiler-mode selective-macro` (already shipped fast macro-argument extraction, all other lowering disabled), **plus the identical per-target diagnostic wrapper installed in every arm**. All arms run the **same genuine survival-player 6×6×6 215-coal native Vein Miner mining event**, original publisher ZIP and same workload/runner settings. The exact native end state must agree across arms: **215 work operations, 1,952 queue-head advances, vmr.run=0, zero remaining ore/source/markers**. Use the existing 9-second idle tick stability gate, bounded 45-second pre-mining RCON forceload timeout, 150-second event observation cap, Linux Server-thread schedstat running-CPU identity/host-quality gates and **no retry after mining begins**. No changes to commands or world setup.

Acceptance requires **1,952 calls in each of the three streams per arm**, **zero** parameter-cache hits/failed macro-argument extraction, exactly **244** valid CPU sample pairs per stream in both EMPTY and TIMED, no failed, negative or omitted intervals, positive CPU denominator and exact source/world-state parity. All raw streams, runner stdout/stderr and pre-mining stage records are archived; invalid or partial events are not interpreted as results.

For each stream, compute **signed corrected per-call CPU** = TIMED mean − EMPTY mean. Multiply by the stream's observed call count and divide by TIMED Server-thread CPU for a **descriptive, inclusive** event share. Report negative and below-clock-floor estimates honestly; do not add overlapping stream fractions or claim a causal speedup across three different boots. Fixed 1/8 systematic sampling can be biased by the order/size of the queue index; this study offers no confidence interval or precise exclusive parse-cost estimate.

## Precommitted decision

- If the **inclusive** original `vanilla_macro_instantiation` or `macro_total` CPU projection is below **5%** of Server-thread event CPU, **stop**: even removing the entire measured span would be too small a credible route toward the project's existing 15% real-workload promotion gate.
- If **5–15%**, treat as an ambiguous intermediate band; obtain better addressability/variance evidence and/or a distinctly larger real workload before implementing an optimizer. Do not run a 30-boot campaign.
- Only if **at least 15% inclusive** AND above the clock floor, inspect the exact vanilla parsed template and its substitution/semantic contract to design a narrow specializer with typed NBT path handling and safe fallback; require explicit tests for negative/large indices, absent paths, callback success/failure, result/return, command quota, nested execution, source context and macro error behavior. A separate **unmodified instrumentation-off** paired causal campaign with the 15% interval requirement would then be needed before any production promotion.

**Important comparability limit:** the target wrapper and its own `MacroTemplateCompiler.extractArguments`/cache lookup are diagnostic additions to the ordinary shipped selective-macro implementation. Their observed `macro_total` and `argument_extraction` spans are not untouched production costs. `delegate.instantiate` still calls the original vanilla macro implementation, but the wrapper and measured call shape can perturb it. Even a high reported fraction would require confirmation in the unwrapped production path before any optimizer proposal.

This is a **CPU mechanism screen**, not a forecast of performance savings, and does not authorize new command transformations merely because 1,952 macro instances were parsed.
