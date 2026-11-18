# COMPILER-EXEC-003 — dynamic command-entry and ordinary-callback census

**Status:** Accepted **descriptive** native entry/callback census on 2026-11-18, with exact workload state parity. **No performance or optimization claim.** This is the next compiler-coverage investigation on the existing `work/compiler-coverage` branch and draft PR #10, after [COMPILER-ACCEPTANCE-002](compiler-runtime-acceptance-002.md).

## Question and hypothesis

The accepted compilation/instantiation census recorded `2,361` executable-chain declines and `221` terminal-only chains, but these are **not dynamic execution counts**. In particular, `vm:detection/upsert_target` contains two commands rejected 30 times apiece at compile time; `vm:operation/claim` has a nested return/function path declined twice; `vm:queue/drain` is known to have a hot macro queue path.

**Question:** Which of the named command entries are actually reached during one genuine native 6×6×6 Vein Miner event? For ordinary Brigadier commands, how often does the final terminal `Command.run` callback execute? Is the missed compile surface in a hot runtime path, or only loaded/expanded code?

The target functions are explicitly allowlisted: `vm:queue/drain`, `vm:queue/enqueue_faces`, `vm:queue/enqueue_diagonals`, `vm:detection/upsert_target`, `vm:detection/acquire_target`, `vm:detection/verify_mined_stat`, `vm:operation/claim`, `vm:durability/damage_vanilla_pickaxe`, plus deliberately cold `vm:admin/adjacency_faces`.

## Observation boundaries

1. **Entry reached** increments immediately before the existing `UnboundEntryAction.execute` action of a particular `InstantiatedFunction` entry is delegated. This is a real runtime event, **not** successful command execution. Forked `execute` chains may evaluate zero or many contexts after this stage; entry reaching is neither leaf invocation count nor instruction quota consumed.
2. **Ordinary callback entered** increments at the real Brigadier `Command.run` callback of the terminal executable. Counts can exceed entry counts under forks. **CustomCommandExecutor** instances (notably function/return-like operations) are never replaced by an ordinary callback wrapper and their `callbacks` column means **unobserved**, not zero actual work.
3. Rows are grouped by function ID and **0-based entry index**, not text matching on a potentially expanded macro argument. One truncated example input is retained to make the site reviewable. A repeated macro may have multiple expansions but the same index. This is **not** unique dynamic command-text cardinality.
4. All counters are disabled unless `FC_COMPILER_EXEC_CENSUS=true`, `FC_COMPILER_EXEC_CENSUS_NAMESPACE=vm`, and an exact nonempty `FC_COMPILER_EXEC_CENSUS_FUNCTIONS` allowlist are supplied. In this configuration the existing function-builder wrapper also admits allowlisted macro functions; their expanded actions get wrapped only once when instantiated and cached. No new Mixin or production default is introduced.
5. A RCON `exec-census-start` command resets site counts after the pre-event registration and setup. `exec-census-stop` freezes counts immediately following work completion, before printing any audit rows. Incomplete events are invalid. Site registration is bounded to 1024 per-function/index keys; any overflow invalidates the measurement. Input examples are truncated at 240 characters.

## Native experiment

Use the original Vein Miner 5.3.0+26.3 ZIP with SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`, Fabric Minecraft 26.3, a survival player and the unmodified real mining packet sequence. The existing `run_veinminer_profile.py` performs the same post-event world-state and scoreboard checks as the accepted studies.

| Arm | Function path | Intended interpretation |
| --- | --- | --- |
| `wrapper` | Wrapper enabled, command compiler off, selective macro fast path off; allowlisted function-entry/callback instrumentation | Delegated-command **baseline execution census** |
| `score-add` | ScoreAdd parser/compiler opt-in, no fusion/direct scheduler, same entry/callback instrumentation | Effect of enabled terminal specialization on **counts and control-flow parity**, not performance |

Both arms have counters and are explicitly diagnostic. Do not compare time, tick time or CPU under this intervention. Require build, Python conservation tests, original ZIP hash, exactly one completed native event/arm, positive `vm:queue/drain` entry control, zero `vm:admin/adjacency_faces` entries, no overflow, and matching native end-state metrics (`work_after`, `remaining_ore`, `source_block_remains`, `queue_head_delta`) across arms. If a counter or native parity check fails, **do not reinterpret the failed event as a valid performance result**.

The report parser `scripts/analyze_compiler_execution.py` validates a single start/end pair, unique site IDs, namespace scope, legal custom-executor classifications, and conservation of both entry and ordinary-callback totals. The workflow `research-compiler-execution.yml` archives `build/benchmarks/COMPILER-EXEC-003/results.json`, per-arm `*-exec-census.log` and runner logs.

## Accepted native result — November 18, 2026

The [native COMPILER-EXEC-003 run #44387363283](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44387363283) **passed** the Java build, all seven synthetic census parser contracts, original Vein Miner publisher hash, both genuine 6×6×6 survival mining events, start/stop marker conservation, exact namespace and target allowlist, and zero overflow. Each arm completed **215** ore work units with **zero** remaining ore and source block, and **1,952** queue-head increments. The existing [COMPILER-ACCEPTANCE-002 control workflow](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44387363682) and ordinary CI also passed this branch revision. Raw per-site logs and full JSON are preserved as the `compiler-exec-003-native-raw` artifact attached to the run.

| Target function | Reached entries, wrapper control | Reached entries, ScoreAdd enabled | Interpretation |
| --- | ---: | ---: | --- |
| `vm:queue/drain` | **17,568** | **17,568** | Nine entries × **1,952** reached per entry; 4 ordinary callbacks × 1,952 = **7,808** in each arm |
| `vm:queue/enqueue_diagonals` | **4,320** | **4,320** | 20 `execute positioned … run function` entries × **216**; custom executors |
| `vm:queue/enqueue_faces` | **1,296** | **1,296** | Six of the same positioned-function family × **216**; custom executors |
| `vm:operation/claim` | **3,440** | **3,440** | 16 entries × **215**; nested `return run function` entry reached, branch outcome not measured |
| `vm:durability/damage_vanilla_pickaxe` | **3,225** | **3,225** | 15 entries × **215**, but only 215 ordinary leaf callbacks in this fixture; conditions matter |
| `vm:detection/acquire_target` | **3,978** | **3,825** | 153 entries × 26 vs 25 detector iterations, a timing-dependent count difference |
| `vm:detection/verify_mined_stat` | **1,593** | **1,534** | 59 entries × 27 vs 26 scans |
| `vm:detection/upsert_target` | **78** | **75** | Three entries × 26 vs 25 scans; not truly cold, but relatively sparse |
| `vm:admin/adjacency_faces` | **0** | **0** | Predeclared deliberately cold control passed |
| **Total selected entries** | **35,498** | **35,283** | These are reached entry counts, not successful commands or CPU cost |

The entire 215-entry between-arm discrepancy is attributable to **one additional detector iteration** in the control arm (153 + 59 + 3 = 215). It does not demonstrate an optimization effect. Both native arms produced the same required world and queue state. No timing improvement is claimed from these counters.

### Cross-study result: a genuinely active compiler rejection

Cross-checking the [accepted COMPILER-ACCEPTANCE-002 archive](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44379699409) with these specific entry IDs confirms:

- `vm:queue/enqueue_diagonals` — **20** source command entries were classified `chain_executable_declined`; all 20 reached their action **216 times** in the native event.
- `vm:queue/enqueue_faces` — **six** further `chain_executable_declined` entries of the same `execute positioned … run function vm:queue/enqueue_here` shape, each also reached **216 times**.
- Together, the **26 statically declined sites reached 5,616 command entries per accepted native event**. Their terminal executable is a `CustomCommandExecutor`; this study does not count actual child-function calls, callback results, or avoidable CPU inside that executor. Nevertheless, this is a real dynamic exposure, not an extrapolation from static token frequency.
- `vm:detection/upsert_target` has real activity (25–26 entries reached for each command), including its previously repeatedly declined `execute as ... run tp` and conditional summon/function patterns. The repeated *compile count* of 30 was **not** a dynamic invocation count.

### Important counter asymmetry

The wrapper-control arm recorded **10,134** ordinary Brigadier callback entries; the ScoreAdd-enabled arm recorded **12,094**. In `vm:detection/acquire_target` alone, the count was 338 versus 2,300. **Do not interpret this as extra commands successfully executing.** The compiled modifier chain in `ScoreAddPrototype.compileChainedModifiers` can replace a conditional source stage with a compiled terminal callback that internally evaluates the condition. The callback then begins even if a branch is false, whereas vanilla may never enter the terminal callback. Those `Command.run` observations are real but **do not represent an invariant semantic boundary across these two implementations**. For conditional commands, report the entry reach count and avoid outcome comparisons unless success/branch gating is independently instrumented. The custom-executor callback column is unobserved, not proof of zero work.

### Decision and next gate

**The executable coverage gap is real, but no new optimizer is yet justified.** The highest-volume uncovered pattern is the positioned child-function call used during queue expansion (5,616 reached entries); do **not** return to generic ScoreAdd callback inlining, whole-server scheduler replacement, or global NBT rewriting. The next narrow question is whether these 26 repeated `execute positioned … run function` sites spend a **material fraction of server-thread CPU in compiler-addressable execution/context/function setup**, as opposed to required `enqueue_here` world/scoreboard work. Reuse validated execution counts, but measure that cost separately without these counters and preserve exact nested-call, result/return, fork, quota and macro semantics before attempting lowering.

## Decision rule

- If the specific previously declined `vm:detection/upsert_target` entries are cold during the mining event, **do not** prioritize their lowering from compilation frequency.
- If a missed pattern is reached frequently, first distinguish entry reaching from actual downstream callback execution and identify its compiler-owned avoidable CPU. **No compiler transformation is authorized from entry counts alone.**
- If an ordinary callback is already specialized but the chain remains `terminal-only`, distinguish vanilla modifier handling from semantically necessary state mutations. Do not infer saved CPU from the number of wrappers.
- Any later real optimization must preserve explicit fork, return, result/success, quota, error/feedback, and macro cache behavior; it must clear the existing paired, non-instrumented causal real-event promotion threshold.

**This investigation deliberately stops at execution exposure and does not add a new scheduler profiler or change the command-lowering implementation.**
