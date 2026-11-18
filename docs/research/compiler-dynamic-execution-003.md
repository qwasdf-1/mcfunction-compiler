# COMPILER-EXEC-003 — dynamic command-entry and ordinary-callback census

**Status:** Protocol implemented; awaiting an accepted native run. **No performance or optimization claim.** This is the next compiler-coverage investigation on the existing `work/compiler-coverage` branch and draft PR #10, after [COMPILER-ACCEPTANCE-002](compiler-runtime-acceptance-002.md).

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

## Decision rule

- If the specific previously declined `vm:detection/upsert_target` entries are cold during the mining event, **do not** prioritize their lowering from compilation frequency.
- If a missed pattern is reached frequently, first distinguish entry reaching from actual downstream callback execution and identify its compiler-owned avoidable CPU. **No compiler transformation is authorized from entry counts alone.**
- If an ordinary callback is already specialized but the chain remains `terminal-only`, distinguish vanilla modifier handling from semantically necessary state mutations. Do not infer saved CPU from the number of wrappers.
- Any later real optimization must preserve explicit fork, return, result/success, quota, error/feedback, and macro cache behavior; it must clear the existing paired, non-instrumented causal real-event promotion threshold.

**This investigation deliberately stops at execution exposure and does not add a new scheduler profiler or change the command-lowering implementation.**
