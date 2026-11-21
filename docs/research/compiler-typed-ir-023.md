# COMPILER-IR-023 — Tag membership, mutation and filtered-index invalidation

**Status (2026-11-20):** Stage 1 SHA-pinned static source audit ACCEPTED; Stage 2 mapped method inventory in progress, not yet native-accepted. This document precommits the semantic and measurement gates. No tag-index runtime, selector replacement, changed compiler mode, speedup evidence or production promotion. Existing branch `work/compiler-coverage`; PR #10 remains draft/unmerged. The new source-audit workflow is manual-only.

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

The initial mapped inventory exposed a **mapping correction**, not a successful mutation-frequency run: the actual official-mapped `Entity` method is `entityTags(): Set<String>`, **not** `getTags()`. The first inspector rejected the stale expectation [in workflow #44863303102](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44863303102). The corrected official-method inspection requires `entityTags` and the actual tag methods. The first run's read-only disassembly nevertheless established:

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

## Stage 4 — exact command-to-command visibility fixtures

Build native 26.3 vanilla-versus-research-disabled and eventual index-on differential tests in separate fresh JVMs:

1. Tags added and removed between consecutive selectors, including repeated no-op add/removes.
2. Tag change inside nested child function followed by parent resumption; same-tick and reentrant callback/queue insertion.
3. Spawn/load, removal/kill, unload/reload and dimension transition across selection commands.
4. `@s`, typed `@e`, positive and negated tags, failed/empty selectors, limits, sorting, multiple worlds, missing scoreboard objective, permissions.
5. Low function-command quotas, callback/result forwarding, return/return-run function and tracing where reachable.

Compare original selected entity identities **and order**, scoreboard states, callbacks, quota behavior, errors, and queue/frame continuation; equality of counts alone is inadequate. Explicitly label cases not yet exercised. The exact observed Blastback command contains a per-entity score guard, so selector membership must never be mistaken for terminal scoreboard eligibility.

## Stage 5 — feasibility decision before an optimizer

Precommit **STOP** when one or more is true: native mutation coverage is incomplete; order/visibility cannot be preserved; invalidation requires world scanning; update/synchronization cost plausibly consumes the narrow whole-event selector budget; or instrumentation cannot distinguish real candidate filtering from its own overhead. No threshold has yet been calibrated; select quantitative ones before interpreting actual native frequency data.

Only after these gates pass could a narrowly allowlisted, opt-in filtered-index prototype be justified. The original selector remains exact fallback. Prove full native parity before **uninstrumented placebo-controlled same-work A/A+A/B** CPU comparison. IR-022's approximately 2.9–4.8% descriptive selector CPU shares are *inclusive*, not a promised improvement. Any future index must preserve Minecraft's world lifecycle, source predicates, ordering and scheduler, without global polling.

**Current disposition:** Stage 1 original-publisher source audit accepted; mapped API inventory under validation. Lifecycle observer, native mutation-frequency measurements, command-to-command differential fixtures and CPU/index experiments are **not yet completed or accepted**.
