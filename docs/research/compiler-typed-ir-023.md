# COMPILER-IR-023 — Tag membership, mutation and filtered-index invalidation

**Status (2026-11-20):** Stage 1 SHA-pinned static source audit ACCEPTED; Stage 2 mapped method inventory ACCEPTED; Stage 3 bounded original Blastback mutation-frequency census ACCEPTED (two independent two-JVM matrices); Stage 4a native same-queue visibility and direct backing-Set bypass ACCEPTED (two independent two-JVM matrices). The prior default-off IR-016–019 native semantic regressions passed. **STOP for an addTag/removeTag/lifecycle-hook-only tag index:** concrete native eligibility changes bypass those hooks. No index, production promotion or causal CPU speedup. This document precommits the semantic and measurement gates. No tag-index runtime, selector replacement, changed compiler mode, speedup evidence or production promotion. Existing branch `work/compiler-coverage`; PR #10 remains draft/unmerged. The new source-audit workflow is manual-only.

## Starting evidence and what it does NOT prove

The accepted IR-022 original Minecraft 26.3/Blastback event counted 4,075,002 and 4,084,845 successful type tests across independently booted PLAIN modes. Only 326,192 (8.00%) and 320,284 (7.84%) passed the native **combined** selector predicate. Its exact command in `erb:restore/job_tick`, at zero-based command index 4, is:

```mcfunction
execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] if score @s erb.job = #active erb.job run scoreboard players set #needs_restore erb.tmp 1
```

About 92% of **type-qualified candidates** failed that entire predicate, but the original `EntitySelector.getPredicate` can combine more than the two tag checks. Neither the individual tag rejection frequency nor the cost of checking tags was measured. The existing 47–49 ns per-combined-test signed correction was smaller than the EMPTY clock-control mean. An index is an **unproven hypothesis**, not justified by multiplying IR-022 totals by a presumed saved predicate cost.

## Stage 1 — original publisher source audit (added)

`scripts/ci_typed_ir023_source.py` operates on only the unmodified original Blastback Hotfix 3 26.3 publisher ZIP, SHA-256 `8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90`. It fails closed if the exact original selector changes or no longer occupies index 4. It classifies literal sites for watched-tag add/remove, related selector reads, entity NBT edits, `Tags` references, summoning, killing, and unresolved macro commands, with bounded source examples. It must not convert static source occurrences to runtime frequencies or infer entity identity from a textual tag command.

The source report is `build/reports/COMPILER-IR-023-SOURCE/source-audit.json`. A manual-only GitHub workflow can acquire the exact pinned ZIP; publisher bytes are never uploaded as research output. The independent synthetic auditor tests cover pin failures, exact-source drift, tagging, lifecycle paths, NBT ambiguities and the non-optimization flag. The pinned source audit and all four synthetic auditor tests passed in [GitHub Actions #44863183534](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44863183534), with original-publisher SHA and index-4 command verified.

### Accepted static results and exact watched-tag writes

The unchanged 9,414,337-byte original publisher ZIP contains **21,318 functions** and **269,141 noncomment command lines**. Exactly one full-line target selector is present. The auditor found **four static watched-tag additions** and **one static watched-tag removal**:

| Function | Source index (0-based) | Exact watched-tag mutation |
| --- | ---: | --- |
| `erb:capture/store` | 0 | `tag @s add erb.block` |
| `erb:capture/store_air` | 0 | `tag @s add erb.block` |
| `erb:restore/accept_existing` | 0 | `tag @s add erb.verified` |
| `erb:restore/verify_one` | 7 | `tag @s add erb.verified` |
| `erb:restore/audit_failed` | 0 | `tag @s remove erb.verified` |

The same source-only classification finds **35,813 tag-add command sites** and **153 tag-remove sites** for *all tag names*, **29 related selector/tag-read lines**, **eight summons**, **40 kill lines**, **23 macro-placeholder commands**, **eight NBT `Tags` references**, and **two entity NBT-write lines**. Those two NBT edit lines modify `data.saved_nbt` and `Age/Invulnerable`, not the tracked `Tags` fields directly. The eight literal `Tags` references are initial marker summon compounds, not observed runtime mutations of existing watched-tag memberships.

**Interpretation:** The original datapack has a very small set of *explicitly written watched-tag source locations*, but this supplies **no bound on their dynamic execution frequency**. In particular, `erb.block` is added as part of capture and `erb.verified` is toggled during restore auditing, so any index would require immediate same-queue visibility, not eventual per-tick refresh. Kills/removals can invalidate references without changing tags. External entities/mods/chunk events remain unmeasured. Counts do not determine tag rejection within the combined predicate.

[Archived source-audit artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44863183534/artifacts/14690897051) includes the bounded exact source examples.

## Stage 2 — map native 26.3 mutation and index lifecycle boundaries

Inspect the **actual** Loom-mapped `Entity.addTag/removeTag/getTags`, `Entity.load`/tag deserialization, `Entity.setRemoved`, world-level entity addition, dimension transfer and indexed entity storage. Verify method descriptors from the exact mapped JAR before writing Mixins. A cache that only observes `/tag` commands is incomplete: direct game/mod tag mutations, NBT loading, entity construction, world unload/reload and cross-dimension transfers must be covered or cause conservative invalidation.

Questions to verify against native code: whether unsuccessful duplicate add/remove calls mutate anything; whether the watched set can be changed outside addTag/removeTag; whether entity tag changes are immediately visible to the next command in the same execution queue; whether unloaded, removed or dimension-transferred references can survive in a proposed index; whether tagged predicates also depend on features, AABB, permissions or other source-sensitive state; whether the original iteration/sort/limit order is stable or must be delegated.

If any transition cannot be reliably observed without a general full-world scan or excessive per-entity bookkeeping, stop the index experiment or use an exact fallback at the unsupported boundary. Do not rely on a per-tick global poll.

### Mapped 26.3 implementation finding — invalidation must cover the backing set

The initial mapped inventory exposed a **mapping correction**, not a successful mutation-frequency run: the actual official-mapped `Entity` method is `entityTags(): Set<String>`, **not** `getTags()`. The first inspector rejected the stale expectation [in workflow #44863303102](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44863303102). The corrected official-method inspection verifies `entityTags`, `addTag`, `removeTag` and `setRemoved`, and completed successfully in [mapped Minecraft 26.3 inspection #44863425889](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44863425889). The first run's read-only disassembly nevertheless established:

- `Entity.entityTags()` returns its underlying `tags` set, not a defensive immutable copy.
- `Entity.addTag(String)` delegates to `Set.add`, returning its success result (after enforcing the 1,024-tag guard); `removeTag(String)` delegates to `Set.remove`.
- The original `TagCommand` uses `Entity.addTag/removeTag` to implement ordinary `/tag` commands.
- `Entity.load(ValueInput)` directly calls `tags.clear()` then reloads the serialized `Tags` list into the same set, **without calling addTag/removeTag**.
- `Entity.setRemoved(RemovalReason)` delegates removal notification through `EntityInLevelCallback.onRemove`.

**Correctness consequence:** Wrapping only addTag/removeTag cannot maintain a complete tag-index revision counter even for vanilla serialization/load; the exposed backing set also allows other Java code to mutate membership without these methods. A full index would need to address all these mutation paths and lifecycle callbacks, preserve selector iteration order, and still handle arbitrary modded consumers. Observing original datapack `/tag` commands is useful for *frequency estimates* but not a proof of general cache correctness. A mutation probe scoped only to addTag/removeTag must label its coverage as partial.

## Stage 3 — native mutation-frequency census

Use original Blastback and a bounded **unchanged** one-TNT event window, reusing IR-022's source hash, pre-event witnesses, actor checks and Linux CPU-quality gates. Add passive, explicit-start/stop research counters (no CPU clocks initially): watched-tag successful adds, successful removes, failed/no-op add/remove attempts, marker spawn/load/removal/dimension transitions, selector visits, selected entity counts, and entities for which membership transitions from eligible to ineligible and vice versa. Distinguish command-initiated mutations from other native mutation sources where possible.

Do **not** use a global log of individual entity IDs, allocate a new object on every candidate, double-evaluate a predicate, or replace the original selector. Counters are not a no-overhead baseline. A full lifecycle coverage claim requires both mapped injection proof and adversarial semantic fixtures; otherwise label the observer partial.

For meaningful economics, report **per original selector scan**: observed eligible size, candidate volume, successful membership changes, lifecycle invalidations, and a conservative upper bound on index update work. Count duplicate attempts separately from effective membership changes. Source tag mutation counts and runtime mutation counts must remain separate quantities.

## Stage 3a — first accepted original native mutation-frequency census

The opt-in IR-023 observer runs only with `FC_CPU023_NAMESPACE=erb`, `FC_CPU023_MODE=control|plain` and explicit bounded `functioncompiler cpu023-start/cpu023-stop` commands. It observes the original mapped `Entity.addTag/removeTag/load/setRemoved` methods and the original `PersistentEntitySectionManager.addEntity/startTracking/stopTracking` methods. The observer does **not** replace or reorder any native method, selector, callback or stored entity, and it retains no entity references. Original selector volume comes from simultaneous IR-022 **CONTROL**, never delegated candidate/predicate wrappers. Both runs use untouched SHA-pinned Blastback Hotfix 3, identical pre-event witness/template checks and a tagged one-TNT event.

**Accepted two-JVM native run [#44864099421](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44864099421)** ([original results artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44864099421/artifacts/14691032944)): Java25/Minecraft26.3 build and all 023 static tests passed; SHA-pinned original publisher verified; two 30-second new-server windows passed original actor, before-state and selector-exposure gates; no missing, invalid or irreconcilable native counts; Linux Server-thread host-quality tests passed. CONTROL counts were zero by design. Post-event template equality is **false in both arms**, consistent with the earlier unresolved Blastback complete-restoration oracle; no full-world restoration or identical-work parity is claimed.

| Exact observation | CONTROL | PLAIN observer |
| --- | ---: | ---: |
| Game ticks in bounded window | 588 | 600 |
| Exact original `execute as` selector visits | 1,245 | **1,240** |
| Native selected entity sources | 324,546 | **317,320** |
| Successful add `erb.block` on markers | Unobserved (control) | **3,278** |
| Successful add `erb.verified` on markers | Unobserved | **3,278** |
| Successful remove `erb.verified` | Unobserved | **27** |
| Add/remove unsuccessful/no-op attempts for watched tags | Unobserved | 0 |
| Observed membership enters (from tag mutation) | Unobserved | **3,305** |
| Observed membership leaves (from tag mutation) | Unobserved | **3,278** |
| `Marker` load callback returns | Unobserved | **3,282** |
| Accepted marker manager additions / visibility tracking starts | Unobserved | **3,282 / 3,282** |
| Marker removal / tracking end | Unobserved | 1 / 1 |

**Per selector scan:** 6,583 successful watched-tag changes / 1,240 scans = **5.3089 successful tag changes per original selector invocation** in this specific 30-second event. All 6,583 membership transitions reconcile exactly with those successful tag mutations (3,278 block adds + 27 verified removals enter; 3,278 verified adds leave). Mutation rates during the window are not necessarily uniform, and an average **does not** establish the worst-case burst/invalidation cost.

The `Entity.load` callback count **does not mean 3,282 disk/chunk reloads**: entity construction and summon-NBT loading can also reach the native load path. Likewise a tracking event and a tag mutation of the *same entity* are counted in separate channels and must not be added as unique entities. The 317,320 selector sources are not 317,320 distinct marker objects. Direct `entityTags()` mutable-set operations outside the explicit methods remain unobservable. IR-022's separate earlier four-JVM candidate-filter statistics cannot be treated as exact per-candidate counts in this IR-023 control-only selector run.

Both server CPU totals are **descriptive quality diagnostics only**: they are separate JVMs, not paired identical-work A/B samples, and neither measures removable index work or a speedup. The study establishes that watched-tag membership is mutated repeatedly during real Blastback restoration, although it changes far fewer times than the number of earlier observed type-qualified candidate tests. This favors investigating a narrowly scoped index *only after* complete invalidation and native scheduling semantics are validated.

### Independent native replication — accepted

A second, independently booted two-JVM matrix was [completed successfully under original workflow run #44864099421, attempt 2](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44864099421/attempts/2), archived as [native replication artifact #14690613661](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44864099421/artifacts/14690613661). The new servers independently verify publisher bytes and original source, original tagged TNT and witnesses, native CTRL/PLAIN selector scoping, zero control-only mutation counters, full metric conservation and Linux Server-thread host-quality. Again neither restored world reaches complete template equality, so we assert no world-restoration success and no CPU causality.

| Native original observation | First PLAIN JVM | Independent PLAIN JVM |
| --- | ---: | ---: |
| Exact original selector invocations | 1,240 | 1,242 |
| Native selected source results | 317,320 | 319,343 |
| Successful `erb.block` adds | **3,278** | **3,278** |
| Successful `erb.verified` adds | **3,278** | **3,278** |
| Successful `erb.verified` removes | **27** | **31** |
| Effective entry into watched-tag eligibility | 3,305 | 3,309 |
| Effective exit from watched-tag eligibility | 3,278 | 3,278 |
| Successful watched-tag mutations | **6,583** | **6,587** |
| Successful watched-tag mutations / selector visit | **5.3089** | **5.3035** |
| Marker `load` callback returns | 3,282 | 3,282 |
| Accepted marker storage additions / tracking starts | 3,282 / 3,282 | 3,282 / 3,282 |
| Tracking starts with currently eligible watched tags | 886 | 1,318 |

The ratio of watched-tag mutations per exact selector visit is consistent in these two bounded original Blastback events; the varying eligible-at-tracking count **warns against treating lifecycle stage populations as fixed**. There were zero no-op watched-tag add/remove attempts in both PLAIN arms and no direct proof that no other Java code modified `Entity.entityTags()` through its exposed mutable set. Reproduction does not remove that coverage gap.

**Decision:** Continue only with event-order/native-visibility semantic fixtures and inspection of all possible backing-set mutation paths. Do not implement a tag index on the assumption that addTag/removeTag or NBT load hooks form a complete invalidation model. An average of ~5.3 mutations per selector call demonstrates low observed relative frequency, not an isolated CPU saving, index maintenance cost, source-order guarantee or permission to change result ordering.

The original native census workflow is now **manual-only** after both accepted attempts. Draft PR #10 remains unmerged; production compiler settings are unchanged. Disabled Mixin hooks may still add overhead, which this experiment has not independently isolated.

## Post-observer native regression acceptance

The [IR-023 native semantic regression workflow #44864492693](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44864492693) passed all four independent Java25/Minecraft26.3 original-game suites after installing the **new IR-023 Entity and PersistentEntitySectionManager Mixins**, with the new mutation probe unconfigured/default-off:

| Original regression suite | Fully matching vanilla state observations |
| --- | ---: |
| IR-016 mixed typed regions, fallback and direct scheduling | **126/126** |
| IR-017 dynamic score guard / source / reentrant behavior | **168/168** |
| IR-018 entity `@s` binding, guarded operations and dispatch barriers | **87/87** |
| IR-019 conditional function dispatch, callbacks, quotas and native child scheduling | **84/84** |

These tests establish preserved behavior for their **tested fixtures**, not complete support for arbitrary mutated tag-set operations, production-wide correctness or zero disabled-Mixin overhead. No index or selector replacement was active. The four-suite regression workflow has been archived as manual-only alongside the twice-accepted real-world mutation census workflow, and all prior IR-022 workflows remain manual-only.

## Stage 4 — exact command-to-command visibility fixtures

Build native 26.3 vanilla-versus-research-disabled and eventual index-on differential tests in separate fresh JVMs:

1. Tags added and removed between consecutive selectors, including repeated no-op add/removes.
2. Tag change inside nested child function followed by parent resumption; same-tick and reentrant callback/queue insertion.
3. Spawn/load, removal/kill, unload/reload and dimension transition across selection commands.
4. `@s`, typed `@e`, positive and negated tags, failed/empty selectors, limits, sorting, multiple worlds, missing scoreboard objective, permissions.
5. Low function-command quotas, callback/result forwarding, return/return-run function and tracing where reachable.

Compare original selected entity identities **and order**, scoreboard states, callbacks, quota behavior, errors, and queue/frame continuation; equality of counts alone is inadequate. Explicitly label cases not yet exercised. The exact observed Blastback command contains a per-entity score guard, so selector membership must never be mistaken for terminal scoreboard eligibility.

### Stage 4a — native same-queue command semantics and explicit Set-mutation bypass ACCEPTED

The original Minecraft 26.3 `EntitySelector` and vanilla function execution queue were exercised in two separately booted Java25/Minecraft26.3 servers per matrix: native research-mod with no mutation census enabled, and the same original commands with passive `FC_CPU023_MODE=plain` enabled **only during the direct-set case**. The *test-defined* `fc_ir023` datapack is not the original publisher Blastback pack; the earlier SHA-pinned Blastback mutation census remains separate evidence. The test-only `fc_ir023_raw_tag` command is registered **only** when `FC_IR023_VISIBILITY_HARNESS=true`, checks `Marker` and `fc023.fixture`, and calls `entity.entityTags().add/remove` directly with the two watched `erb.*` tags. This is an adversarial fixture operation, not a vanilla `/tag` command and not a compiler transformation.

Both [native validation #44867340232 attempt 1](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44867340232/attempts/1) (artifact [#14692163597](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44867340232/artifacts/14692163597)) and [independent attempt 2](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44867340232/attempts/2) (artifact [#14692257366](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44867340232/artifacts/14692257366)) completed the build, all 3 new static fixture tests plus all 4 prior IR023 native-counter tests, and **five matching native scoreboard snapshots per arm**. The earlier invalid cold-start attempts were not admitted as observations; they revealed headless chunk/entity lookup warm-up races. The accepted harness now *fails closed* unless a bounded, unmeasured same-queue marker summon/select/kill readiness fixture passes. Warm-up was completed before any watched mutation counters were enabled.

| Native exact-source fixture | Both native and passive-observer results in both independent matrices |
| --- | --- |
| Same-function `/tag` add, duplicate add, add `verified`, remove `verified`, remove `block` | Eligibility observations **0, 1, 1, 0, 1, 0** |
| Nested child `/function` verifies marker, then parent resumes | `parent0=1, child0=1, child1=0, parent1=0` |
| Same-function marker NBT summon, verify tag, kill, next selector | Eligible observations **0, 1, 0, 0** |
| Native `sort=nearest,limit=1` on two tracked markers; verify nearest | Selected scoreboard identifiers **11, then 22** |
| Direct `entityTags()` Set add/remove of `block` and `verified` | Eligibility observations **0, 1, 0, 1, 0** |

**The decisive invalidation witness:** In *each* accepted passive-observer direct-set fixture, the native selector registered all five eligibility observations correctly, while `add_block_attempt/changed/noop`, `remove_block_*`, `add_verified_*`, `remove_verified_*` and `eligible_entered/left` remained **zero**. The *same* window recorded **one** marker load callback, **one** accepted storage-add event and **one** tracking-start event. Thus no choice of invalidating only from current method hooks or entity lifecycle boundaries can detect the four successive eligibility transitions of this already registered entity. The observer's zero tag-mutation values are a verified **coverage hole**, not evidence of a static tag membership. This also establishes the Minecraft selector's immediate observation of direct backing-Set edits in these tested commands.

**Limits:** This experiment demonstrates native scoreboard results and two distinguishable nearest selections, not proof of identical arbitrary entity-UUID result sequences, all tie-order cases, arbitrary mod interactions, entity NBT reloads, chunk unload/reload, dimension transfer, multiverse permissions, per-command quota interruption, callback/return-run forwarding or full Blastback restoration. Those remain separate differential fixtures if a future proposed optimizer requires them. Both JVMs have the same gated research mod installed, although neither uses an alternate selector. No CPU measurement or speedup claim was made.

**Decision (STOP):** The current `addTag/removeTag/load/setRemoved + PersistentEntitySectionManager` hook set is **not a complete invalidation mechanism**. A general cached tag-membership index using those hooks would become stale under the verified original `entityTags()` mutation path; no safe unconditional index-on trial is admitted. A future candidate must first solve **all** backing-Set mutations without altering identity, order, world lookup, scheduler or mod compatibility, or make explicit original-selector fallback mandatory on every unsupported path. Neither an unsupported global poll nor a speculative per-tick refresh proves same-queue semantics. Given the existing small and non-isolated CPU selector budget, no new index cost trial is justified by IR023 alone.

The native visibility workflow was archived as **manual-only** after both accepted independent matrices. Draft PR #10 remains unmerged and the production compiler, selector and scheduler are unchanged.

## Stage 5 — feasibility decision before an optimizer

Precommit **STOP** when one or more is true: native mutation coverage is incomplete; order/visibility cannot be preserved; invalidation requires world scanning; update/synchronization cost plausibly consumes the narrow whole-event selector budget; or instrumentation cannot distinguish real candidate filtering from its own overhead. No threshold has yet been calibrated; select quantitative ones before interpreting actual native frequency data.

Only after these gates pass could a narrowly allowlisted, opt-in filtered-index prototype be justified. The original selector remains exact fallback. Prove full native parity before **uninstrumented placebo-controlled same-work A/A+A/B** CPU comparison. IR-022's approximately 2.9–4.8% descriptive selector CPU shares are *inclusive*, not a promised improvement. Any future index must preserve Minecraft's world lifecycle, source predicates, ordering and scheduler, without global polling.

**Current disposition:** IR023 source audit, mapped JVM inspection, independently replicated original Blastback mutation census, independently replicated native same-queue visibility/bypass fixtures, and post-observer default-off IR016–019 semantic regressions are accepted. The source, inspection, census, regression and visibility workflows are archived manual-only. **General tag-index invalidation STOP gate triggered** by the directly proven mutable-Set write path. No index, production selector rewrite, scheduler rewrite, CPU speedup claim or completed Blastback restoration oracle. PR #10 remains draft and unmerged.
