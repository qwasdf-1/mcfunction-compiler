# Scheduler and command-runtime research archive

**Archive index prepared 2026-11-18.** This file records the completed diagnostic PRs so they can be **closed without being merged into production**. The branches and their original Actions runs remain distinct research evidence. Do not interpret closing a PR as proving a production feature or deleting its backing Git branch.

## Why archive rather than merge the eight draft PRs

The project goal is a **Minecraft function compiler** that can compile, specialize or lower selected datapack program operations while preserving vanilla semantics and demonstrating **causal real-workload improvement**. The accumulated diagnostic branches contain hundreds of changes to standalone profiler Java classes, method-redirection Mixins and CI; most are off by default, but **installed-but-disabled Mixin overhead was never independently certified**. Merging all that instrumentation into `main` would introduce unqualified runtime hooks for no proven compiler benefit.

The existing `research/sched-attr-028-result-callback-routing` branch already contains the cumulative SCHED-ATTR-024–028 implementation history and reports; #21–23 are separate diagnostic lines. Use that branch as the historical code archive, not as the base for the next compiler feature. The new **`work/compiler-coverage` branch starts cleanly from `main`** and is intended to be **reused across subsequent compiler-coverage audits and concrete lowering proposals** until review/merge, instead of branching for each measurement.

## Preserved diagnostics and outcome

| Original draft | Scope | Result or stopping decision |
| --- | --- | --- |
| [#1 — SCHED-COMP-021](https://github.com/qwasdf-1/mcfunction-compiler/pull/1) | CPU-time JFR sampling feasibility | **Rejected**: 5/10/20ms samples exceeded the declared >5% dropped-sample ceiling. No accepted scheduler-share estimate |
| [#2 — SCHED-COMP-022](https://github.com/qwasdf-1/mcfunction-compiler/pull/2) | Sparse typed ScoreAdd callback CPU | **Diagnostic only**: 1.29–1.58µs/callback; projected ~0.111–0.134% Server-thread CPU in two three-arm datasets. Not a causal optimizer effect |
| [#3 — SCHED-ATTR-023](https://github.com/qwasdf-1/mcfunction-compiler/pull/3) | Queue-loop vs queue-entry CPU | **Inconclusive exclusive residual**: raw ~0.96% queue-minus-entry difference smaller than clock overhead sensitivity; no usable near-zero scheduler-overhead bound |
| [#4 — SCHED-ATTR-024](https://github.com/qwasdf-1/mcfunction-compiler/pull/4) | Vanilla execution task path census | **Accepted census**: 194,017 dequeued actions; 80,799 BuildContexts, 58,770 ContinuationTask, 28,265 ExecuteCommand, 26,145 CallFunction observed entries |
| [#5 — SCHED-ATTR-025](https://github.com/qwasdf-1/mcfunction-compiler/pull/5) | Sparse CPU on execution task types | **Accepted descriptive attribution**: BuildContexts and ExecuteCommand contain significant CPU but also real game work; smaller CallFunction/continuation corrections near clock floor |
| [#6 — SCHED-ATTR-026](https://github.com/qwasdf-1/mcfunction-compiler/pull/6) | Modifier/Brigadier/real command execution calls | **Accepted descriptive attribution**: executable path includes real Command.run and result callbacks; cannot call the enclosing CPU removable dispatch |
| [#7 — SCHED-ATTR-027](https://github.com/qwasdf-1/mcfunction-compiler/pull/7) | Command-context copy vs result callback | **Accepted descriptive attribution**: callback ~21.43% projected Server CPU; copy small and near clock floor. Does not mean callback can be suppressed |
| [#8 — SCHED-ATTR-028](https://github.com/qwasdf-1/mcfunction-compiler/pull/8) | Actual result delegate + exact /execute store callsites | **Accepted mechanism identification**: 256 selected NBT result-store callbacks account for 99.968% of observed stateful callback CPU in final accepted single-event screen; those mutate real NBT state, not pure queue housekeeping |

Important raw runs and artifacts:

- SCHED-COMP-022 accepted [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44169241336) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44169241336/artifacts/14367636370), plus [repeat](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44170251809)
- SCHED-ATTR-024 accepted [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44188671911) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44188671911/artifacts/14375507746)
- SCHED-ATTR-025 accepted [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44190487217) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44190487217/artifacts/14377425739)
- SCHED-ATTR-026 accepted [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44232819056) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44232819056/artifacts/14396745579)
- SCHED-ATTR-027 accepted [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44238748694) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44238748694/artifacts/14398144505)
- SCHED-ATTR-028 accepted underlying delegate [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44242914760) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44242914760/artifacts/14400732108), and final site-specific [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44246032167) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44246032167/artifacts/14401204131)
- Pinned source-only Vein Miner storage/entity destination [run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44353718983) / [artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44353718983/artifacts/14450090969)

**Artifact retention caveat:** GitHub Actions artifacts expire under their configured retention policy. The written conclusions in the PR descriptions and committed research docs remain necessary even if raw artifact downloads stop working.

## Decision: return to compiler-owned optimizations

The general scheduler-replacement hypothesis does not currently have evidence for promotion. Most of the apparent command-dispatch gap can be traced to **actual Minecraft NBT state mutation**, including commands that Bellows optimizes at the runtime layer for entity accessors.

The next project is **COMPILER-COVERAGE-AUDIT-001**: reconcile actual compiler parser/lowering eligibility with the pinned Vein Miner source, *existing* H2-first runtime activation and performance results, and explicit default-on/off feature flags. The separate compiler branch is based on clean `main`, not the profiler stack.

A compiler candidate must have a semantic transformation hypothesis for a recognized IR/program pattern, measured hot real-workload exposure, deterministic success/failure/callback/return/fork parity, and a genuine paired causal improvement. Do **not** treat static command frequency, NBT callback CPU or loop-entry counts as a savings forecast.

## Working-branch policy

1. **One ongoing `work/compiler-coverage` branch and PR** for the current workstream; amend/update that branch on subsequent related tasks.
2. Close historical draft PRs as **completed research, intentionally unmerged** once this archive index is visible, retaining the original branches until deliberate manual cleanup. Do not squash their experimental Mixins into `main`.
3. Only propose a distinct PR if a completed, reviewable compiler feature is actually ready to merge; keep that PR's diff limited to eligible compiler behavior, tests, and documentation.
4. Revalidate results after any future changes to the Minecraft version, mapping or publisher asset pin.

The GitHub integration used for this archive supports branch creation, file changes and PR closure, but **not direct deletion of Git refs**. Old remote branch names may therefore remain after PR retirement. They can be manually pruned later without losing this index or the associated GitHub PR history.
