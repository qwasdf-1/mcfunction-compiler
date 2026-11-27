# Integration-001 — maintained experimental typed compiler

Status: draft candidate; no merge authorization. Base main 976806f9f7d2a72cab51837c5927bd9b176f8bab; accepted research checkpoint 9dcd9fc6386aad8ef21400cfcb7e2a4d051e739c (checkpoint/ir047-accepted). Keep PR #10 and research history intact. Candidate branch is based directly on main, not the research branch.

## First extraction slice

Import only changed runtime Java sources necessary for the accepted compiler and its validation, not historical research workflows or reports. Remove the following research-only classes from the candidate: CompilerAcceptanceAudit, CompilerExecutionCensus, CompilerPositionedCpuProbe, CompilerQueueCpuProbe, CompilerRestoreCpuProbe, CompilerMacroLoadCpuProbe, CompilerEntityWritebackProbe, CompilerForkBreakdownProbe, CompilerSelector022Probe, CompilerTagMutation023Probe, CompilerTagVisibility023Harness, IR041CompileProbe. Do not install the 11 historical instrumentation mixins: CompilerEntityDataLoadCpuMixin, CompilerEntityWritebackCpuMixin, CompilerForkContextChainMixin, CompilerForkContinuationMixin, CompilerForkEntitySelectorMixin, CompilerForkSourceMixin, CompilerQueueBuildCpuMixin, CompilerQueueExecuteCpuMixin, CompilerSelector022Mixin, CompilerTagMutation023EntityMixin, CompilerTagMutation023ManagerMixin. Remove their entry hooks, parser counters, macro timing/census wrappers and research commands. Load test scoreboard mixins only when explicit adversarial fixture flags are enabled. Prevent activation of rejected IR010 revision cache, unqualified IR036 backend cost selector and IR025/028 fork executor (remaining shared code will be pruned separately). Preserve normal compiler semantics, the existing main legacy config/feature behavior and typed feature flags pending public configuration design.

## Admission and evidence

Supported candidate surfaces: bounded typed mutations/conditions/binary operations, mixed opaque barriers and exact native fallback, reentrant-safe queue, IR037 prepared metadata, IR038 comparisons and min/max, IR039/040 compound and native arithmetic, IR043 native function dispatch, IR044 terminal guards, IR045 native stores, IR046 value and IR047 preflight reuse. Direct typed scheduler opt-in (not a general CPU claim). No cached selector membership or cross-call scoreboard snapshots. No general macro typed coverage promised. Existing main features stay unchanged unless independently audited. All typed modes remain opt-in with explicit namespace.

## Merge gates

A: source inventory, clean extraction, Java25 build and ordinary CI. B: default-off exact native state parity with main and disabled-overhead CPU screen (independent boots, same host, main-vs-main and candidate-vs-candidate control, predeclared 5% tolerance and stable windows). C: exact native differential and original publisher state parity against pinned checkpoint, opt-in regression of accepted incremental improvements; compare full candidate and checkpoint separately. D: remove remaining dormant experiment implementations, test-only command/resource packaging and public configuration/status audit; docs and migration, compatibility and release gates. No promotion solely from successful build or existing historical studies. Scope of this first slice: A and preparing B/C, not release approval.

## Traceability

Full evidence stays on research branch. See [IR046](https://github.com/qwasdf-1/mcfunction-compiler/blob/9dcd9fc6386aad8ef21400cfcb7e2a4d051e739c/docs/research/compiler-typed-ir-046.md), [IR047](https://github.com/qwasdf-1/mcfunction-compiler/blob/9dcd9fc6386aad8ef21400cfcb7e2a4d051e739c/docs/research/compiler-typed-ir-047.md) and original PR #10.
