# Mercury source audit

**Evidence level:** Static review of the pinned source snapshot. No build,
integration script, test, or benchmark was run.

## Snapshot and scope

Reviewed [Mercury commit `193d65b`](https://github.com/clang-mc/Mercury/commit/193d65bd031debf6539136427339f9ce1619696c), dated 2026-05-23. Its build properties target Minecraft 1.21.4 with Yarn `1.21.4+build.8`, Fabric Loader 0.17.2, and Fabric API 0.119.4+1.21.4. The source uses Apache-2.0. This is a substantially older target than 26.3, so it is an architectural reference rather than evidence of 26.3 internals.

## Design observed

Mercury builds parse and semantic IR during datapack reload, compiles eligible
functions into JVM bytecode, and uses multiple fallback paths for commands it
does not specialize. Its current source has a Tier 1 baseline compiler,
macro-argument prefetch, and guarded Tier 2 recompilation for hot callers.

The loader overwrites the vanilla function reload method and reconstructs the
resource-to-function pipeline. A second overwrite captures parsed actions at
the `FunctionBuilder` boundary. This gives broad control over loaded functions,
but creates a large version-sensitive integration surface. A 26.3 prototype
should prefer a narrower hook only if it can observe the needed parsed object
and prove reload, tag, and function identity are preserved.

Tier 1 generally remains inside vanilla's command-action queue. Compiled blocks
can complete, return through the frame, suspend to a vanilla action, or
suspend for macro prefetch. Unknown commands are dispatched through a binding
or requeued as vanilla work. The engine explicitly decrements command quota in
its bound-command path. Directly lowered commands and compiled paths must be
audited separately for quota and tracer behavior: a source scan found the
explicit debit in the bound-command helper, while specialized paths can bypass
that helper. This is a static parity question, not a confirmed runtime defect.

Scoreboard values are cached in execution frames and flushed at normal,
return, suspension, and exceptional exits. Mixins watch selected scoreboard
mutations to synchronize active frames. This technique depends on all relevant
mutations reaching those interception points; other mods and commands are
important cases for runtime validation.

The macro pipeline first materializes vanilla `ExpandedMacro` actions, then
profiles calls and prepares guarded specializations. A specialization guard
compares expected NBT arguments before a compiled path is selected. The
synchronous expansion cache key is a 32-bit rolling argument hash combined
with the macro object's identity hash; the source lookup uses that key without
an equality check against the original argument tuple. Hash collisions are
therefore a review and adversarial-test target before relying on cached macro
materializations for correctness.

## Tests and benchmark tooling

The source has two focused Java test classes for JIT context composition and
bytecode compiler regression behavior. Its RCON integration script exercises
selected score/data lowering, macro prefetch and specialization, and generated
artifacts. The benchmark script measures the same datapack workload with
Mercury enabled and disabled, uses a high command-chain limit, runs warmups and
four measured passes per mode, and prints timing ratios. That is useful
engineering tooling, but it does not compare a 26.3 build, verify all vanilla
observable effects, or establish a portable performance claim by itself.

## Relevance to this project

- Keep fallback actions at command boundaries so unknown or mod-provided
  commands retain vanilla execution.
- Treat frame-local caching, command quotas, tracing, return propagation, and
  macro argument guards as explicit semantic contracts.
- Consider tiered specialization only after the simpler path is correct and
  evidence shows compilation cost and hotness policy are worthwhile.
- Avoid assuming Mercury's mapped class names, mixin targets, or scheduler
  behavior apply to the 26.3 target.

## Follow-up questions

- For each 26.3 compiled instruction, is the vanilla cost debit and tracer
  event preserved exactly once?
- Do all mutation routes invalidate or flush cached scoreboard slots?
- Can macro cache keys retain equality-checked argument tuples rather than
  relying on a hash alone?
- What compile threshold and maximum generated-code size fit this project's
  workload and reload budget?
