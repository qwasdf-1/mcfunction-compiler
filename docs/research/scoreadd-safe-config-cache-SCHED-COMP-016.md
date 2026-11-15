# SCHED-COMP-016 — Production-safe immutable environment overrides, directly versus vanilla

**Status:** **Completed, accepted against the predeclared gates** on November 14, 2026; dynamic config reload and quota parity passed, all 12 independent JVM boots passed host quality and native A/A median interval includes zero. A direct small gain over native was supported on the specified synthetic scoreboard workload, not real gameplay.

## Motivation and code boundary

In SCHED-COMP-015, our scoreboard command wrapper calling the original vanilla scoreboard callback was **+36.3252 signed log-%** CPU versus an equivalent native function. The existing typed callback was another **+5.4436 log-%** over that wrapper. When a *research-only* implementation skipped repeated configuration-flag lookups under explicitly fixed environment values, the typed path improved by **−52.0874 log-%** (about −40.6% ordinary relative CPU). However, SCHED-COMP-015 did **not** directly randomize its fully optimized path against native, and freezing dynamically reloadable flags would be incorrect.

This follow-up starts from **main**, not the scheduler-replacement research stack. Only three hot configuration accessors now cache *immutable environment override values* at process start:

- `FC_SCORE_ADD_PROTOTYPE`
- `FC_SCORE_ADD_TIMING`
- `FC_SCORE_ADD_METRICS`

An absent or blank `FC_SCORE_ADD_PROTOTYPE` environment override remains **dynamic**: every call evaluates `CompilerConfig.isScoreAddEnabled() || ProbeConfiguration.fusedRegionPrototypeEnabled()`. Any explicit nonblank override uses the same old `Boolean.parseBoolean` semantics and wins over config reload. Timing and execution-metrics overrides have always defaulted false and are non-reloadable. The rest of the mod's configuration, command semantics, scheduler, and production optimization defaults are unchanged.

A strictly **research-only** `FC_SCORE_ADD_LEGACY_NAMESPACE` allows one named function namespace to retain the old `System.getenv`-on-every-command behavior. If unset/blank, it activates no namespace. It exists to make a direct causal comparison inside the same JVM without keeping the earlier research-only objective-cache and direct-scheduler prototypes.

## A. Hard semantic gates, in separate Minecraft JVMs

### A1. Dynamic configuration with no override

The first production Minecraft 26.3/Java 25 JVM does **not** set `FC_SCORE_ADD_PROTOTYPE` and starts with `enabled=true, score_add=true` in `config/function-compiler.json`. It enables *diagnostic-only* `FC_SCORE_ADD_METRICS=true`. After normal datapack function compilation, write `score_add` to true, false, true in turn; issue `function_compiler_probe reload` each time; read back live `score_add_prototype_enabled` status; invoke an existing, already-specialized 4-line function; and verify **exactly 4, 0, 4** typed callback increments, while each invocation still changes the scoreboard by exactly 4. This demonstrates **true per-call reload behavior**, not just status echo.

### A2. Fixed override precedence + vanilla command quota

The second JVM sets `FC_SCORE_ADD_PROTOTYPE=true`, `FC_SCORE_ADD_TIMING=false`, `FC_SCORE_ADD_METRICS=false`, with the benchmark legacy namespace explicitly named. It confirms all four function families compile correctly: two native controls compile no ScoreAdd, and cached/legacy compile all N commands. It verifies live `minecraft:max_command_sequence_length` gamerule **set and numeric readback** at quotas 2,3,4,8,16,32,64, comparing native/cached/legacy after 16-command functions. Low quota must actually truncate and high quota must finish all 16 commands; all three paths must agree at each quota. Restore original quota even on failure.

Set the JSON config `score_add=false` then issue the mod's reload command. An explicit environment `FC_SCORE_ADD_PROTOTYPE=true` must **still win**, and the optimized cached path must perform all expected scoreboard changes. Restore the configuration, then run 20 exact calls of each N=2000 family. No timing samples from either diagnostic JVM enter the statistical performance analysis.

These are the minimum semantic gates for this narrow study. They do not claim exhaustive callback/trace/error, all-criteria, or real-mod behavior; production promotion still requires standard differential suites and one realistic datapack check.

## B. Direct native comparison in 12 independent JVMs

Use **12 fresh production Fabric servers** with an identical compiler JAR and Java 25 flags. All four arms coexist in each JVM and have **byte-identical `scoreboard players add #x fc_sched 1`** source commands:

| Arm | Namespace | Runtime path |
| --- | --- | --- |
| A | `fc_cache_native` | Original parsed vanilla callback; specialization excluded |
| A' | `fc_cache_native_null` | Byte-identical original callback; placebo |
| B | `fc_cache_legacy` | Original `ScoreAddCommand` with repeated environment/config lookups |
| C | `fc_cache_cached` | Same typed body with cached immutable environment overrides |

All four stay under the vanilla scheduler, no fusion, no alternative queue, no selective macros, and no bytecode backend. Normal `/function` invocation and response processing remain in place. Verify per-function compiled command counts before any timing. All diagnostic counters, JFR and phase timing are **OFF** in these timed JVMs.

Preregistered seed `16016`, four ABBA/BAAB contrasts per boot: **A/A' placebo; B/A original slowdown; C/B caching improvement; C/A direct optimized-versus-native**. Use a Latin-square rotation over four temporal block positions, repeated three times: each contrast occurs at every position exactly three times. Each comparison has six ABBA and six BAAB orientations. All 12 boots include 16 measured windows (4 per contrast), each invoking 2,000 command functions **220 times**: **440,000 exact score additions per window**. Prewarm all arms for 120 calls, plus the existing bounded server CPU stabilization qualification. No windows or boots are dropped post hoc.

Primary effect for each contrast/boot: `100 × (mean ln(B server_thread_CPU_ns_per_command) − mean ln(A server_thread_CPU_ns_per_command))`, where **CPU is Linux server-thread running CPU** and log-% negative is faster. Analyze **one paired contrast per boot**, report signed median and distribution-free exact ≥95% order-statistic interval (12 boots: 96.14% achieved coverage). Do **not** use RCON wall time or individual windows as independent observations.

Quality gates: all exact scoreboard work; stable CPU warmups; no cgroup throttling in any timed window; available runqueue-delay fraction ≤25% per window; A/A' exact interval must contain 0. Failed gates → no supported comparative claim. A material gain requires C/A interval upper bound ≤−15 signed log-%; a smaller interval entirely below zero is a supported narrow screening gain but not a production promotion.

## Stop conditions

If semantic reload or quota parity fails, **stop before timing** and fix the actual behavior rather than easing the gates. If the direct optimized-versus-native interval includes zero, report it as inconclusive even if B/C looks faster. If C loses to native, do not promote it simply because it beats the old typed prototype. Regardless of outcome, **no claim of real-datapack benefit** follows until an independently controlled native-versus-cached end-to-end test is completed.

The 015 benchmark's speculative summed intermediate effects are not substituted for this direct randomized comparison. Do not generalize these results to arbitrary selectors, callbacks, objective rules, or the scheduler replacement research.

**Files:** `src/main/java/dev/functioncompiler/ProbeConfiguration.java`, `ScoreAddCommand.java`, `scripts/ci_safe_config_cache.py`, `tests/test_safe_config_cache.py`, `.github/workflows/research-scoreadd-config-cache.yml`. Raw output: `build/benchmarks/SCHED-COMP-016/{reload,diagnostic,timing}.json` and every Minecraft boot log. CPU harness dependencies are pinned copies from earlier validated research and pinned `mc-tooling` checkout; they do not enable other research optimizations.

## Completed results — 12-JVM SCHED-COMP-016

**Authoritative run:** [GitHub Actions #43561655160](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43561655160). Raw artifact [`sched-comp-016-safe-config-cache`, ID 14100897767](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43561655160/artifacts/14100897767) contains the separate reload, quota diagnostics, `timing.json`, and per-boot server logs.

### Semantic proof

The separate **no-environment-override** JVM demonstrated configuration `score_add` on → off → on through the actual `function_compiler_probe reload` command, with actual typed callback increments **4 → 0 → 4** and identical scoreboard work **4 → 4 → 4**. This proves the fast accessor does **not** accidentally freeze live `CompilerConfig` when the environment override is absent. In the second diagnostic JVM, the explicitly set environment override remained authoritative even with JSON `score_add=false`.

The Minecraft 26.3 `minecraft:max_command_sequence_length` gamerule was actually set and read back, and produced **exactly equal command results** in native, original-getenv and cached variants at quotas 2,3,4,8,16,32,64: **1,2,3,7,15,16,16**, respectively. These are verified truncation values; the earlier 014 invalid-old-gamerule test is not used.

### Main controlled CPU result

All **12 independent JVMs** completed, with four ABBA/BAAB contrasts and four timed windows each (**192 total windows**), exactly **440,000 scoreboard additions per timed window**, and no failed host-quality gates. The placebo interval includes 0; one boot (boot 1) contained an unusually large A/A effect **−50.28 signed log-%**. That boot and all other observations were retained, not excluded to improve the result.

| Contrast (B vs A) | Median signed log-% | Exact 96.1426%-coverage median interval (signed log-%) | Ordinary median CPU difference |
| --- | ---: | --- | ---: |
| Native placebo vs native | +1.9834 | [−2.7900, +3.5675] | +2.0% |
| Legacy per-command getenv ScoreAdd vs native | +22.2565 | [+17.4057, +23.9698] | +24.9% |
| Cached immutable env override ScoreAdd vs legacy | **−28.7286** | **[−34.1968, −26.0843]** | **−25.0%** |
| Cached immutable env override ScoreAdd vs native | **−8.9230** | **[−10.9948, −7.3180]** | **−8.5%** |

Positive = slower and negative = faster server-thread CPU per exact source command. Signed log-% is `100×ln(B/A)`; convert to ordinary percent as `100×(exp(logpercent/100)−1)`. The direct cached-vs-native interval corresponds to approximately **7.1%–10.4% lower CPU** on the exact fixture.

**Preregistered verdict:** `cached_path_small_gain_vs_native_supported`. It is a supported directly randomized *synthetic* performance effect, below the 15 signed log-percent materiality threshold. It is **not** a claim that all compiled mcfunctions, all scoreboard commands, or real gameplay are faster. Because of the one unusually large placebo-window contrast, independent replication before production promotion would be prudent despite the original A/A median interval rule passing.

### Implementation and production disposition

The research branch also includes a named `FC_SCORE_ADD_LEGACY_NAMESPACE` comparison path and copied CPU harness dependencies, so do not merge its whole diff as a production optimization. The pure production change is isolated in [draft PR #15](https://github.com/qwasdf-1/mcfunction-compiler/pull/15), consisting only of the three immutable env override accessors with live config fallback. Keep it a draft until real-datapack screening and broader semantic/regression review.

The follow-up [SCHED-COMP-017](https://github.com/qwasdf-1/mcfunction-compiler/pull/14) is a separate native Vein Miner playerbot event comparing **legacy vs cached ScoreAdd** on a verified publisher datapack. It does not change the conclusions or validity of the controlled CPU test; a real null result would limit practical relevance without negating the synthetic mechanism.
