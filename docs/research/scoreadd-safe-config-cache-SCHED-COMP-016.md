# SCHED-COMP-016 — Production-safe immutable environment overrides, directly versus vanilla

**Status:** Predeclared protocol and implementation. No performance result until the current CI test, native/legacy/cached crossover, placebo, and host-quality gates pass.

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
