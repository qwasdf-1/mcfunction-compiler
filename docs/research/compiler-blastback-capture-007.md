# COMPILER-BLASTBACK-007 — source-pinned Blastback capture classifier preflight

**Status: ACCEPTED READ-ONLY SOURCE AUDIT; NATIVE OPTIMIZATION GATE NOT OPEN.** No production or research optimizer, scheduler patch, new Mixin, behavior modification, CPU sampling campaign, or TNT world benchmark was introduced. Existing branch `work/compiler-coverage`, draft PR #10.

## Question

After COMPILER-CPU-004, CPU005 and MACRO-006 rejected their Vein Miner hypotheses, can a *different* genuine 26.3 datapack provide evidence of a high-CPU, compiler-owned uncovered pattern?

Blastback Hotfix 3 is the strongest structural lead in the existing project archive. The prior 19-pack source screen identified **7,580 tick-reachable adjacent parsed-candidate runs** (longest 32) among a very large set of generated block-state classifiers. The prior genuine 1-TNT pilot sampled substantial function work but **failed restoration integrity** after a 180-second sample plus five-minute settle: the source/template remained different, and block markers, a restore job and protected-item state remained. The no-TNT tick-dispatch pilot is valid but intentionally exercises only a cheap periodic `#tick_id` ScoreAdd.

**Do not count lexical command runs as executed CPU or reinterpret the failed TNT restoration pilot as an accepted end-to-end performance result.**

## Accepted original-publisher archive and method

The [read-only COMPILER-BLASTBACK-007 Actions preflight #44547009562](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44547009562) passed on **2026-11-19**:

- Original Modrinth Blastback Hotfix 3 for Minecraft 26.3, published version `dMtA8r0n`, archive `Blastback-Hotfix-3-26.3.zip`, verified **by downloaded bytes** with SHA-256 `8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90`. The Modrinth metadata omitted the SHA-256 field; the runner did not substitute a different version or omit its byte-level check.
- Reused the existing `scripts/screen_adjacent_regions.py` source scanner; followed source-level function call closure from `erb:capture/store`; inspected exact generated `execute if block ... run scoreboard players set @s erb.state N` command bodies.
- Checked the **actual** `scripts/run_blastback_profile.py` injected block palette (stone plane, gold/diamond/redstone/emerald witnesses and TNT) against its named generated source readers.
- Archived a compact JSON report (`build/benchmarks/COMPILER-BLASTBACK-007/source-audit.json`). No server was booted; no dynamic activation, parser acceptance, CPU, or world-state parity was inferred.

## Source findings

| Observation | SHA-verified source result | Meaning |
| --- | ---: | --- |
| Parsed datapack functions | **21,318** | Original publisher archive, not executed count |
| Functions reachable from `erb:capture/store` via direct source calls | **6,779** | Conservative source graph; tags/macros may be missed |
| Generated state-reader functions with exact conditional scoreboard assignments | **1,062** | Static candidate table count |
| Those candidate readers reachable via the direct capture call graph | **1,062** | *Potential* dispatch reachability, not evidence of block matches |
| Parsed candidate adjacent runs from tick-reachable source | **7,580** | Existing source screen reproduced |
| Longest source run | **32** | Examples: `minecraft:acacia_fence`, `minecraft:acacia_fence_gate` |

The concrete generated acacia fence and fence-gate readers each comprise 32 `execute if block ~ ~ ~ ... run scoreboard players set @s erb.state N` commands. The original `erb:capture/store` actually invokes `erb_generated:read/root`, followed by block-property tags, conditional block NBT storage and capture/dependency logic. This is **real mutable block-state capture work**; neither evaluating a block predicate nor recording a matching state is automatically removable compiler overhead.

### Unmodified fixture palette cross-check

| Known setup block | Original generated `read_state` commands |
| --- | ---: |
| `minecraft:stone` | **1** |
| `minecraft:gold_block` | **1** |
| `minecraft:diamond_block` | **1** |
| `minecraft:redstone_block` | **1** |
| `minecraft:emerald_block` | **1** |
| `minecraft:tnt` | **2** |
| `minecraft:air` | No corresponding generated per-state reader identified |

All six **known deliberately placed block types** with matching state readers have at most two classifier commands. This is an important contrast with the impressive-looking 32-way table examples.

**Limitation:** The fixture does not enumerate every naturally generated block in its 17×17×17 volume. Absence of acacia fences in the explicitly injected palette does **not** prove zero native 32-way dispatch. The exact runtime block-state histogram and per-reader invocation counts have **not** been measured.

## Decision and narrow next gate

**Do not implement a Blastback state-dispatch specialization or launch a full compiler-off/fused pairing campaign on this evidence.** The source graph provides credible possible shapes, but neither dynamic 32-way classifier exposure nor a stable capture/restoration completion gate has been established. The large generated codebase alone does not provide an addressable CPU denominator. The previously tested real-world fused-region campaign on Vein Miner also failed its ≥15% promotion gate, so broadening fusion speculatively is specifically unwarranted.

Only reopen this candidate with a **single separate read-only native capture-stage diagnostic** that establishes all of the following before timing:

1. A real publisher-unmodified TNT event, SHA-pinned source, unchanged test world, and a *capture-specific* start/stop invariant independent of the still-incomplete restoration stage.
2. Captured block types/states actually observed and **specific named generated reader entry counts**. Reached commands must be distinguished from successful conditions and from costly callbacks.
3. A bounded, reproducible state/progress parity rule across any future arms; do not repurpose a partial or incomplete restoration state as an accepted completed workload.
4. Evidence of substantial **compiler-owned** avoidable CPU (not just real block state detection and NBT saves) before any proposed lowering, bytecode/fusion backend work, or multi-JVM performance run.

This study closes the **source-screening stage**, not the native activation or CPU-attribution stage. It does **not** claim Blastback is slower, faster, compiler-optimizable or already ready for a causal campaign. Alternative existing pack pilots are also below a reliable 15% compiler-owned opportunity on current evidence: Dynamic Lights has 1.6% addressable active sampled CPU, Spawn Animations 10.4% in a short transient capture, and Everything Clings' entity population did not remain stable.

**Decision:** Research only; no new optimizer. The next engineering task is a valid representative, state-observed Blastback capture fixture—not another parser implementation.
