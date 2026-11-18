# COMPILER-COVERAGE-AUDIT-001 — compiler-owned opportunities in pinned Vein Miner

**Status:** Read-only static source audit and compiler-coverage reconciliation in progress, independent of the archived NBT/scheduler profiler stack.

## Goal and scope

Identify **which datapack program patterns the compiler could safely transform**, rather than treating all expensive Minecraft command handlers as compiler overhead. Use the original Vein Miner 5.3.0+26.3 publisher ZIP, SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`. No world mutation, no new Mixin, and no NBT accessor rewrite.

**Do not duplicate prior research.** The existing compiler coverage proposal `docs/v1/plans/compiler-coverage-widening-proposal-v0.1.md`, tested `scripts/run_specialization_inventory.py` H2-first census, and `scripts/attribute_specialization_share.py` source-attribution already establish:

- Vein Miner has **266 static adjacent fusable commands in 27 tick-path runs**; an earlier native activation found **164 compiled regions and 718 executed**. The *real paired fusion campaign* still measured ~**+0.69%** median completion (no material benefit, does not meet promotion gate). Counting static eligible sites alone is therefore not a good new-optimizer business case.
- Vein Miner has approximately **23.4% lexically forked execute lines** in the existing H2 census, but H1's actual sampled forked execution share was close to zero in the three studied packs. Do not choose fork fusion based on source frequencies without runtime evidence.
- The expensive native work involved macro argument extraction; the promoted **selective macro argument** feature already covered **11,701/11,701 attempted calls without fallback** in the recorded Vein Miner event and demonstrated a **−29.58% median paired event completion** benefit in the independent confirmatory campaign. It is already default-enabled. Rebuilding an equivalent fast path is not a coverage improvement.
- The scoreboard ScoreAdd callback was only a fraction of a percent of total Server-thread CPU in SCHED-COMP-022, while SCHED-ATTR-028 traced much of the apparent scheduler CPU to required `/execute store ... data` NBT mutation. A global NBT patch is **outside the compiler project** unless justified by a new compile-time IR transformation and causal test.

## Audit layers, not interchangeable metrics

1. **Static source:** `scripts/audit_compiler_coverage.py` verifies the pinned publisher SHA-256, loads the existing H2 tag/function reachability graph, and classifies command lines into macro invocation candidates, lexical fusion/leaf-inlining candidates, fork barriers, known parser roots and other vanilla syntax. The output is intentionally approximate and can **overcount real eligibility** due to Brigadier argument shapes, parent context and macro expansion.
2. **Compiler coverage:** compare the resulting command shapes against `ScoreAddPrototype.EXECUTABLE_COMPILERS` and `MODIFIER_PARSERS` (the actual parsed runtime compiler) and the shipped `CompilerConfig` gates. Presence of `scoreboard`, `execute` or `data` in source code is **not proof** that the corresponding specialization parses every shape.
3. **Real execution:** reuse past native activation and paired CPU/completion evidence; do not claim new dynamic activation from a static ZIP. For new candidates, separately instrument compiled/fallback/execute counts on an exact event and confirm a large enough addressable **compiler-owned** cost before writing an optimizer.
4. **Causal optimization:** a new candidate must prove exact result/store/callback/return/fork and quota parity, with the existing real-workload ≥15% median gain and exact paired-interval acceptance threshold.

## Provisional prioritization, before new source census

| Mechanism | Existing evidence | Current decision |
| --- | --- | --- |
| **Selective macro argument extraction** | Already promoted and measured, zero fallback in hot Vein Miner diagnostic | **Retain and test for regression**, do not duplicate |
| **Generic scoreboard callback inlining** | Small CPU share in SCHED-COMP-022 | **Do not pursue** on current workload |
| **Fused regions** | Eligible and executed but real event gain failed threshold | **Not promoted**; need different compiler-specific fusion hypothesis and dynamic cost |
| **General scheduler replacement** | Nested profiling reaches necessary callbacks/NBT state effects | **Do not pursue** without evidence of avoidable cost |
| **General-purpose NBT store accelerator** | Bellows already optimizes selected entity NBT accessor paths; native callback cost is real state change | **Keep out of compiler scope** |
| **New transformations for actual macros/command patterns** | Static census required; must first demonstrate dynamic miss/fallback and cost | **Study only if source+runtime evidence supports it** |

## Research branch consolidation

This work is on **`work/compiler-coverage` based on clean `main`**, not on SCHED-ATTR-028. Future related coverage tasks will update this **same branch/PR**, rather than stack a new branch for each diagnostic. The prior research evidence and PR links are indexed in [`scheduler-research-archive.md`](scheduler-research-archive.md); that stack must not be merged blindly into production.

## Execution

```sh
python3 -m unittest discover -s tests -p test_specialization_inventory.py -v
python3 -m unittest discover -s tests -p test_audit_compiler_coverage.py -v
# Requires the verified, pinned original publisher ZIP
python3 scripts/audit_compiler_coverage.py --pack veinminer
```

Output: `build/benchmarks/COMPILER-COVERAGE-AUDIT-001/audit.json` and `audit.md`, archived by the read-only GitHub workflow. **No new runtime performance estimate is generated.**

The next compiler change should be chosen only from the completed static categories + prior empirical costs, not a hypothetical performance gain deduced from token frequency.
