# Bellows source audit

**Evidence level:** Static review of the tagged 26.3 source and differential
runtime probes against vanilla 26.3 and Bellows 1.1.2. The probes use the
fingerprinted Minecraft artifact recorded in
[`26.3-internals.md`](26.3-internals.md). They are focused confirmation cases,
not a complete Bellows compatibility suite.

## Snapshot and scope

Reviewed [Bellows release 1.1.0](https://github.com/Smithed-MC/Bellows/releases/tag/1.1.0),
commit [`59f6e80`](https://github.com/Smithed-MC/Bellows/commit/59f6e80514da6022aa4d2afd87bab201c2ed94fd),
dated 2026-09-16. Its build properties target Minecraft 26.3, Fabric Loader
0.19.5, and Fabric API 0.160.6+26.3. The license is Apache-2.0. Its release
note says the target was updated to 26.3 and that an entity-name optimization
was removed because vanilla added it.

The README still describes entity display-name laziness, although that
optimization is absent from the tagged 1.1.0 source. Prefer release-specific
source and notes over README feature lists when they disagree.

The runtime probe used Bellows 1.1.2
(`d0c7218e7e368c7d1473483881540ff78554853ff0a4f0bab098df6b3c753b67`) on
Minecraft 26.3. The source snapshot above is release 1.1.0, so runtime findings
are attributed to 1.1.2 and source explanations remain tied to the reviewed
1.1.0 revision unless separately confirmed against 1.1.2.

The original compatibility baseline compares nine arms: vanilla, Fabric
wrapper-off/on, ScoreAdd-on, fused-interpreted, Bellows wrapper-off/on,
Bellows+ScoreAdd, and Bellows+fused-interpreted. A selected five-arm bytecode
extension and six-arm Bellows + Moonrise 1.2.0 extension were added later. The
literal and fused ScoreAdd fixtures compile and execute under compiler-enabled
stacks; score state and feedback match their compiler-off controls. Selector
and entity-NBT cases also remain equal across the tested compiler-off/on pairs.

## Bellows 1.1.3 follow-up

On 2026-10-29, the user reported that Bellows maintainers closed the
Vein-Miner compatibility issue and released 1.1.3. The official
[Modrinth release metadata](https://api.modrinth.com/v2/version/QoiW2Z70)
identifies the pinned file as `bellows-1.1.3.jar` for Minecraft 26.3/Fabric;
its SHA-256 is
`4d9fc818d0e800c1a7414b4670c676339020749e516a50742bd18c4e3d61055c`. The
changelog says it fixes some NBT paths in data commands that were not updating
correctly. The earlier 1.1.2 workload failures remain historical until
1.1.3's native datapack workload gate passes.

The inspected 1.1.3 jar still declares `nbt.DataCommandsMixin` and
`nbt.EntityDataAccessorMixin`. In the audited 1.1.0 source, those hooks route
`DataCommands` reads/writes through path-filtered entity-data access. Function
Compiler's selective macro prototype instead injects at
`FunctionCommand$2.arguments`, resolves a single macro, and copies only its
requested top-level `CUSTOM_DATA` fields. It bypasses the original
`FunctionCommand.getArgumentTag` serialization path only for that eligible
case. This is a separate entry point and a narrower selection rule, not the
same Bellows implementation. Both address entity-NBT construction, so measure
their combination and retain vanilla differential coverage for the bypassed
path.

The pinned Vein Miner 5.3.0 archive contains both `/data get` and `/data
modify` entity paths as well as `function ... with entity @s data`, making the
1.1.3 change directly relevant to retesting the failed native workload. The
profile harness has separate `bellows113`, `lb113`, and Moonrise stack names.
The Bellows-only compiler-off 4×4×4 run passes its native workload gate:
63/63 blocks, 480 queue increments, and clean source/operation state. This is
one workload-integrity result, not a performance comparison. Lithium+Bellows
1.1.3 also passes a compiler-off 6×6×6 native event: 215/215 blocks, 1,952
queue increments, and clean source/operation state. Two selective-macro
diagnostics on that stack counted 9,546 and 9,547 eligible calls. A ScoreAdd
diagnostic counted exactly 1,952 optimized `#head` executions, matching the
datapack.

Five randomized no-Spark pairs for each prototype then passed exact workload
parity on Lithium+Bellows 1.1.3. Selective macro had a −18.83% median
event-completion change, but its 93.75% interval spans −20.62% to +24.37%.
ScoreAdd had a +3.60% median change (slower), with a −2.04% to +91.11% interval
and one large slowdown. Both are screening evidence only; neither confirms a
gain or regression. The native Vein Miner 5.3.0 workload now also passes on
Lithium+Bellows 1.1.3+Moonrise 1.2.0, with a five-pair selective-macro screen
recorded below. Moonrise 1.2.1 fails to start with the pinned Bellows build.

## Design observed

Bellows targets selector searches and NBT reads/writes with caches and filtered
entity serialization. It uses mixins around entity-selector construction,
entity lookup, data commands, execute-store paths, and entity accessors. Some
hooks target synthetic lambda names or local variables, which increases
mapping/compiler fragility. An optional Moonrise path is selected only when the
relevant classes are present.

### Selector and AABB behavior

In the reviewed 26.3 source, `EntitySelectorMixin.addEntities` routes to the
type/tag cache when the selector has positive tag constraints, even if vanilla
supplied an `absoluteAABB`. The cache query receives the type and predicate but
not the box. Exact 26.3 bytecode inspection shows the box is a separate
argument to vanilla's entity lookup, not folded into that predicate. This
remains a source-level concern for selectors that combine a positive tag with
a spatial restriction such as `dx`, `dy`, or `dz`.

The runtime probe compared positive-tag selectors with `dx`, `dy`, and `dz`
against untagged box selection. It used two box positions, a nearest `limit=1`
case with a nearer out-of-box candidate, and an order-sensitive scoreboard
swap across three nearest-sorted entities. Vanilla, Fabric with wrapper off/on,
and Bellows 1.1.2 with wrapper off/on selected the same entity identities and
produced the same final scores in these cases. This did not reproduce the
suspected AABB omission. The expanded nine-arm matrix also checks positive-tag
distance filtering, score filtering combined with an AABB, positive and
negative tag constraints with a second AABB, and furthest sorting with
`limit=1`. All selected identities match vanilla across Fabric and Bellows
wrapper-off/on and ScoreAdd arms. The cases still do not cover every selector
option, random ordering, or broader entity populations.

The cache stores candidate entities in `HashSet`s. The tested nearest sort
preserved order-dependent command state; arbitrary traversal order and other
sort modes remain open.

### Filtered entity NBT

The runtime probe confirmed that Bellows 1.1.2's entity tag index follows
`data modify entity ... Tags append` and `data remove entity ... Tags` for the
tested zombie: selectors saw the added tag immediately and stopped matching
the removed tags. Common zombie `NoAI`, `PersistenceRequired`, and
`Invulnerable` modify/merge/remove operations also matched vanilla state and
command feedback.

A filtered-load asymmetry was a confirmed Bellows 1.1.2 runtime divergence.
After setting `home_radius=8` and `home_pos=[I;72,64,72]`, vanilla changes
`home_pos` to `[I;80,64,80]` on a `data modify` command and resets it to
`[I;0,0,0]` on `data remove`. Bellows 1.1.2 reported success for both commands
but left the position at `[I;72,64,72]`. The reviewed 1.1.0 source describes an
empty filtered-load `home_pos` branch handled only by `home_radius`; inspection
of the exact 1.1.2 jar confirmed that Bellows' filtered `setData` helper ignores
the filtered setter's decline result on these paths.

The project now includes a Bellows-specific adapter for the filtered
`data modify` and `data remove` paths. When the accessor wraps a `Mob` and the
path's top-level key is `home_pos`, it gets a complete vanilla entity snapshot,
merges Bellows' filtered update into that snapshot (or removes `home_pos` when
the filtered update omitted it), then calls the original vanilla setter. The
full snapshot is necessary: an earlier adapter draft passed Bellows' partial
compound directly and erased unrelated entity tags. The final adapter passed
the tag-index and NBT checks, including preservation of unrelated data.

`data merge` uses a separate Bellows interception path. Its filtered setter
declines this `home_pos` case and Bellows falls back to vanilla; the new direct
merge case confirms the value changes to `[I;76,64,76]`. The expanded nine-arm
matrix now asserts vanilla's exact results for initialization, merge, modify,
and remove, then compares all four Bellows arms (wrapper off, wrapper on,
Bellows+ScoreAdd, and Bellows+fused-interpreted) with vanilla. All four states match: `[I;72,64,72]`,
`[I;76,64,76]`, `[I;80,64,80]`, and `[I;0,0,0]` respectively. This verifies
these focused zombie `Mob.home_pos` paths on Bellows 1.1.2; it does not close
the broader selector or filtered-NBT matrix.

A separate zombie tests the adjacent `home_radius` path. Vanilla starts with
radius 8 and position `[I;56,64,0]`; changing the radius to 12 preserves the
position, and removing the radius makes both fields absent from saved entity
data. The same command feedback and resulting values match across all nine
vanilla, Fabric, ScoreAdd, fused, and Bellows arms. This found no reason to extend the
adapter beyond the verified `home_pos` path.

The filtered `VillagerDataFinalized` loader also contains an explicit no-op.
A focused Minecraft 26.3 probe initialized a villager with the field set to
`1b`, then ran `data modify ... VillagerDataFinalized set value 0b`. Vanilla
and all ten Bellows 1.1.2 arms (wrapper off/on, ScoreAdd, fused-interpreted,
bytecode, and the same five modes with Moonrise 1.2.0) reported success and
retained `1b`. The selected 11-arm run `20261028T164726` passed its normalized
vanilla and same-stack compiler parity checks. This no-op matches the observed
vanilla result for this exact command; it does not establish parity for other
villager fields or filtered NBT paths.

The latest complete nine-arm run is `20261028T110322`; its generated JSON and server
logs are disposable probe output, while artifact hashes and the result summary
are retained in the maintained research records.

### Moonrise 1.2.0 compatibility extension

The original nine-arm probe did not cover Bellows with Moonrise. A focused
six-arm run on 2026-10-28 compared mod-free vanilla with Bellows 1.1.2 plus
Moonrise 1.2.0 in wrapper-off, wrapper-on, ScoreAdd, fused-interpreted, and
bytecode-emitted modes. All six servers started. The five modded arms matched
vanilla for the selected selector identities/order, common entity-data
updates, Bellows tag-index updates, and `home_pos`/`home_radius` observations;
all four same-stack compiler-off/on pairs matched. The `home_pos` adapter
restored vanilla init, merge, modify, and remove values in all four optimized
arms. The pinned Moonrise jar SHA-256 is
`cb4890a8aeb61115b4b57aff3d4ec26c96ffdb4194d28fd7ed9d1365db3aa4d6`; Bellows
and Minecraft fingerprints are unchanged from the baseline. The generated
report was stored under the ignored `build/reports/compatibility-probe/` path
and removed after the findings were summarized here and in the test matrix.

This runtime success is separate from the Dynamic Lights workload result:
Bellows + Moonrise 1.2.0 still fails to produce that datapack's torch-source
tags and light markers. It establishes compatibility for the probe's tested
command paths, not equivalence of every datapack under the stack. Bellows 1.1.2
with Moonrise 1.2.1 remains startup-incompatible because Bellows' selector
mixin cannot find its expected shadow field.

### Bellows 1.1.3 Moonrise follow-up

The focused selective-macro fixture now passes on Lithium 0.26.2 + Bellows
1.1.3 + Moonrise 1.2.0 (`lbm113120`). Mod-free vanilla, same-stack
compiler-off, and selective-macro candidate arms match; candidate activation
counts are 2 direct calls, 2 fallback calls, 3 debug calls, and 20 quota-sweep
calls. The result report is
`build/reports/runtime-probe/macro-20261029T070635.results.json` and records
each pinned jar hash. This is macro fixture evidence; it does not establish
native datapack workload parity on that stack.

Repeating the same three-arm check with Bellows 1.1.3 + Moonrise 1.2.1
(`lbm113`) fails during server startup before the compiler candidate runs.
Bellows' `MoonriseEntityLookupMixin` shadows `EntityLookup.entityById`, which
is absent from Moonrise 1.2.1's target class. The preserved wrapper-off log is
`build/reports/runtime-probe/macro-wrapper-off-20261029T070444.server.log`.
Bellows 1.1.3 therefore remains incompatible with this pinned Moonrise
version; the 1.2.0 macro fixture pass does not change the open native-workload
gate.

### Bellows 1.1.3 selector and NBT matrix

The selected compatibility probe was extended to the working Lithium 0.26.2 +
Bellows 1.1.3 + Moonrise 1.2.0 stack. Run `20261029T154729` compared mod-free
vanilla, Fabric-off, and Bellows-stack compiler-off, wrapper-on, ScoreAdd,
fused-interpreted, and bytecode-emitted modes. All seven arms started. The five
compiler modes match compiler-off for selector identities and ordering, common
entity NBT, Bellows tag-index updates, `home_pos`/`home_radius`, and the tested
modded Brigadier leaf. All five also match the selected vanilla outcomes,
including the verified `home_pos` adapter values. Pairwise compatibility
checks passed.

The run pins Lithium
`0be5b17ef9f6e9244cd07b24b227553a73aec0cf93158cf28099f3094c167f1b`, Bellows
1.1.3 `4d9fc818d0e800c1a7414b4670c676339020749e516a50742bd18c4e3d61055c`,
Moonrise 1.2.0
`cb4890a8aeb61115b4b57aff3d4ec26c96ffdb4194d28fd7ed9d1365db3aa4d6`, and the
Minecraft 26.3 server
`d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64`. The
probe command was:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_compatibility_probe.py --modes \
  vanilla fabric-off lbm113120-off lbm113120-on lbm113120-score-add-on \
  lbm113120-fused-interpreted lbm113120-bytecode-emitted
```

This closes only the selected compatibility fixture on this stack. It does not
establish support for untested commands, selector combinations, or other
filtered NBT paths.

A subsequent full 16-arm run, `20261028T152121`, combined the base Fabric and
Bellows 1.1.2 matrices with the Bellows + Moonrise 1.2.0 arms. It passed the
selected selector, entity-NBT, tag-index, `home_pos`, `home_radius`, and
modded-leaf cases with no failed pairwise or vanilla parity checks. The raw
report and per-arm logs were disposable ignored probe output and have been
removed; the test matrix and this summary retain the result.

The probe also tried modifying a passenger's nested `Tags` through its
vehicle's `Passengers` NBT. The command returned success but left the passenger
tags unchanged in vanilla and all tested Fabric/Bellows arms, so that case does
not demonstrate a lost write relative to vanilla. The separate static concern
about `bellows_setDataFiltered` returning false remains unproven at runtime for
a path where vanilla changes state.

### Tests and claims

The tagged tree has an NBT GameTest focused on filtered entity save/load. It
does not cover every command wrapper and fallback path described above.
Bellows' README reports large workload-specific tick-time reductions; these
are upstream claims, not measurements reproduced for this audit.

## Relevance to this project

- Differentially test selected entity identities and order, not just result
  counts. The initial positive-tag AABB and nearest-order cases pass, but
  broader combinations remain.
- Keep the adapter limited to the verified Bellows 1.1.2 mob `home_pos`
  `modify`/`remove` case. Other filtered entity-NBT paths still require
  independent vanilla differential checks.
- For an optimization that can decline a filtered operation, propagate the
  decline result and invoke the original vanilla operation where required.
- Pin the Minecraft artifact and mixin target descriptors for each supported
  game version.

## Follow-up questions

- Does the selector cache path preserve box, sort, limit, predicate, and order
  semantics beyond the tested positive-tag AABB and nearest-order cases?
- Which filtered NBT paths besides `home_pos` return success without applying
  the vanilla mutation, and which false returns fail to invoke a safe fallback?
- What other mods mutate entity tags or saved entity data outside Bellows'
  cache update hooks?
