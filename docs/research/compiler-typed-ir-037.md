# COMPILER-IR-037 — Prepared typed commands and same-command objective-lookup elimination

**Status (preregistered 2026-11-23): implementation complete on `work/compiler-coverage`; Java build / native differential semantics pending.** This is a **real, reusable compiler transformation** over post-Brigadier typed commands, not a game-engine patch. The compiler is still opt-in; no production defaults or promotion policy change.

## Runtime waste identified

Even after IR-035/036 canonicalization, every typed scoreboard command's shared runtime `State.begin` repeatedly interpreted the immutable validated instruction shape: detect `Conditional`, recover the terminal `Mutation` or `Binary`, rediscover its target, guard and source-operand names/holders, then `State.finish` recovered the terminal and original mutation kind AGAIN to select the correct feedback. The optional source-value revision reader also rediscovered the binary source objective.

The compiler already knows all of that at function construction; it must not redo it every time a repeated datapack function runs.

A second concrete redundancy occurs within *one* guarded/binary command. Example:

```mcfunction
execute if score #g fc_ir matches 1.. run scoreboard players operation #x fc_ir += #y fc_ir
```

All three references name `fc_ir`. The previous runtime called `scoreboard.getObjective("fc_ir")` for target, guard and source, despite no scoreboard mutations or callbacks between those pure name-map lookups. The new compiler can prove their names equal and reuse the **freshly resolved, same-command Objective**. This eliminates up to **two** redundant objective-name lookups per command in such patterns. Ordinary binary `#x fc_ir += #y fc_ir` eliminates one repeated lookup. The exact number is data-dependent; neither case eliminates a score read/write or a Minecraft command.

## Implemented compile-time transformation

`TypedIRPreparedSteps` builds a `Prepared[]` **once per compiled region** from the original immutable `TypedIROptimizer.Plan`. Each descriptor retains:

- The exact original source Instruction, plus predecoded optional guard and optional binary operand shapes.
- Target, guard, and binary operand holder references, flags for dynamic `@s`, and objective name strings. These are immutable identifiers, *not* cached runtime objectives or scoreboard values.
- The **original** feedback kind `ADD`, `REMOVE`, `SET`, or `OPERATION`, with the original literal amount. Signed-delta canonicalization is not allowed to change a REMOVE message to ADD.
- Compile-time equality flags for target↔guard, target↔operand, and guard↔operand objective names. The descriptor constructor validates these flags and the original command shape; a fabricated or reordered descriptor is rejected.

Both typed backends consume the same kind of descriptor:

- The **interpreter** retains its existing immutable original instruction and IR opcode arrays, with a parallel immutable `Prepared[]`. Every typed step invokes `State.begin(prepared)` instead of `State.begin(original)`.
- The **ASM bytecode emitter** gives its hidden class a second final `prepared` array alongside `steps`. Each is read **once** per invocation; emitted instructions pass `prepared[index]` into the new shared runtime begin method. The instruction array remains intact for reentrant vanilla continuation.
- `State.begin(prepared)`, `sourceOperand()`, and `finish()` no longer dynamically classify the terminal opcode or mutation feedback. All original runtime-side semantic work remains: entity resolution, fresh target objective lookup, conditional score evaluation, quota debit(s), trace callbacks, player-score access, mutations, error processing, feedback, and opaque original fallback.
- For equal objective names **inside a single command**, the newly resolved target or guard Objective is reused for the other same-name references. A fresh `scoreboard.getObjective(targetName)` happens again **at the next source command**. There is no cross-command objective caching. Dynamic `@s` ScoreHolders remain resolved live on each execution.
- The exceptional reentrant `QueuedTail` still uses its exact original source instructions; the one-step legacy `begin(original)` prepares metadata on demand in that slow path, avoiding any change in callback interleaving semantics.

The only purity assumption is the vanilla server-thread behavior of `Scoreboard.getObjective` as a side-effect-free, same-thread name-map lookup *between mutations inside one source command*. If another mod intentionally makes repeated `getObjective` reads produce side effects or independently changes the objective registry on another thread, this local load-elimination is not proven equivalent to that non-vanilla behavior. It does not cache through listener callbacks, score writes, function calls, or other source-command boundaries.

## Correctness and quantitative evidence

1. The full Java 25/Minecraft 26.3 Fabric build must succeed, with legacy IR-034/035/036 unit/source contracts, new `tests/test_typed_ir037.py` and IR-017 guarded-binary shape contracts.
2. **IR-017 five-JVM native differential** compares vanilla, old bytecode control, interpreted, new bytecode, and direct scheduler. It includes same-objective guarded binary operations, distinct target/guard/source objective names, range predicates, missing objectives, partial quotas and injected synchronous queue callbacks. The IR-037 diagnostic must report `ir037_objective_lookups_reused > 0` in all three new compiled modes, proving actual execution took the lookup-elision path. All native state and queued-order observations must match original vanilla; legacy control must remain distinct in coverage, not semantics.
3. **IR-008 four-JVM native differential** compares vanilla, fused, interpreted, bytecode with missing/read-only objectives, integer overflow, score aliases, guards, quotas, and feedback-result storage. It establishes that original score state and fallback remain unchanged.
4. **IR-013 six-JVM reentrant differential** requires the three guarded execution modes to match the original vanilla queue under callback insertions and quota truncation; both deliberately unsafe negative controls must still diverge as expected.
5. Raw outcomes, full diagnostics and logs must be archived, including negative results. No retries based on favorable data, post-hoc lowering of acceptance standards, or CPU performance promotion.

The new `ir037_objective_lookups_reused` metric is **diagnostic-only** and counts each actual map lookup avoided within an executed command. It is not a measured CPU-time gain; its count is expected to vary with the fixture's specific instruction/branch coverage.

## Explicit limitations

This is not dead-store elimination, value propagation, score-access caching, or a transformation that reduces the number of source commands. It removes repeated runtime *metadata work* and provably redundant **Objective name-map reads inside one command**. An empirical CPU gain is not established: IR-033's no-treatment A/A study rejected small-effect measurement stability, so an IR-037 speedup cannot be inferred from correctness tests or lookup counts.

The follow-up compiler effort should target broadening legal transformations of commands and module-defined pure operands, not adding game-engine hooks or multiplying profiler studies.

## Results

**PENDING native correctness gates.** Append the exact run/artefact IDs, lookup-elision counts and semantic disposition after the preregistered run.
