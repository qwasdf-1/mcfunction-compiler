# Project reference

## Scope

Explore whether a conservative compiler can improve hot Minecraft Java Edition
function execution while preserving vanilla's observable behavior. The initial
research target is a server-side Fabric mod for Minecraft 26.3.

The project investigates parsed-command specialization, execution overhead,
cost-aware regions, macro specialization, and interoperability with runtime
mods such as Bellows. The implementation plan explicitly leaves backend choice
open pending measurement.

## Non-goals for the initial experiment

- Replacing Brigadier or the global function scheduler without evidence.
- Changing command limits, permissions, results, errors, traces, tag ordering,
  function returns, or visible world behavior for speed.
- Supporting every vanilla or mod-provided command at the outset.
- Duplicating Bellows' indexes or bypassing modded world-operation hooks without
  a compatibility and performance result.
- Depending on the compiler for Minecraft Recrafted gameplay behavior.

## Evidence and source of truth

The research plan labels evidence as exact-target static inspection,
near-version comparison, external reference, hypothesis, or open. The official
26.3 server and classfile artifacts are fingerprinted; queue costs, function
construction, and reload/tag paths have been statically reviewed. The current
ten-arm runtime suite compares mod-free vanilla with nine Fabric modes for 16
direct fixtures, nested returns, vanilla and compiled-region recursion, quota
changes, fork limits 1–12, scoreboard edges, macro behavior, lifecycle, and
debug traces. The disabled
fused-interpreted and emitted-bytecode prototypes preserve the tested vanilla
error, continuation, quota, and `/debug function` behavior, including an error
inside a region followed by later commands and a vanilla queue entry. A
separate injected-failure run confirms bytecode compilation failure falls back
to original entries. A selected Fabric-only modded-command fixture preserves
an unknown Brigadier leaf between eligible compiled regions and matches the
compiler-off control. Focused macro checks cover tuple churn, storage changes,
a hash collision, and invalid arguments across seven modes.

The nine-arm interpreted Bellows compatibility probe covers selector
filtering, entity NBT, tag-index updates, literal and fused ScoreAdd behavior.
A selected five-arm bytecode extension covers vanilla, Fabric compiler-off/on,
and Bellows compiler-off/on. A Bellows adapter restores vanilla mob `home_pos`
results for the tested initialization, merge, modify, and remove cases. The
six-arm Bellows + Moonrise 1.2.0 extension also passes selected vanilla
selector, entity-data, tag-index, and home-position comparisons across the
wrapper-off/on, ScoreAdd, fused, and bytecode arms. The selected Dynamic Lights
datapack still does not produce equivalent output on that stack. Vein Miner
5.3.0 supplies a native-trigger workload for direct ScoreAdd: five Fabric
pairs show no reliable gain, while five Fabric+Lithium and five
Fabric+Lithium+Moonrise pairs trend slower by median with wide ranges; none
demonstrates a reliable gain. The latter campaign included a temporary dormant
diagnostic mixin in both arms. A 2026-11-03 static screen found adjacent
candidate runs in the pack's family detection, but they have no runtime
activation or performance evidence, so fused and bytecode regions remain
unmeasured in a real pack. Compiler-off Vein Miner fails workload integrity on the
tested Bellows-containing stacks, so those are not valid compiler comparisons;
use another workload for Bellows compatibility profiling. Call-path analysis
of all 15 valid compiler-off captures points to repeated `with entity @s data`
macro argument extraction and full entity serialization as a profile-led
candidate; verify a selective-argument prototype before treating it as an
optimization target.
The
fused prototype's server-thread timer completed
ten trials per arm across two randomized sets on one 5,000-command fixture;
its median queue time was 2.014 ms versus 3.399 ms for the vanilla-command
delegate and 3.147 ms for ScoreAdd. This static-fixture result is not a
real-world speedup claim. A 25-cycle reload check held generated-class counts
steady after GC; a PERF-004 comparison found bytecode slower than fused
interpreted for the measured fixture. Dynamic Lights has no eligible
fake-holder additions; Vein Miner has eligible operations but no real-world
fused/bytecode region. Callback attribution is available as an opt-in
diagnostic and has been verified on Vein Miner. Broader callback correctness,
reload-error, mod-compatibility, allocation, and performance gates remain
open. All optimization prototypes stay disabled. The
Fabric wrapper-off control still uses Fabric API and the probe mod.

The prototype source, build target configuration, and recorded runtime evidence
define its current behavior. This project reference and the current-state page
summarize that evidence; the versioned plan records proposals and research
history.

Do not check decompiled Minecraft source into the project. Record concise
method-body notes and exact build fingerprints in the research area. Review
LGPL compliance before reusing MCFC code.

## Initial artifacts

- `docs/v1/plans/minecraft-function-compiler-research-and-implementation-spec-v0.1.md`
  — detailed research and proposed implementation plan.
- `docs/v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv` — 79
  validation cases with dependencies and run status.
- `docs/research/` — curated source notes, toolchain pin, runtime results, and
  external implementation reviews.
