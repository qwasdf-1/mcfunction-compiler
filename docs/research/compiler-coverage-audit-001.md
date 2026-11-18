# COMPILER-COVERAGE-AUDIT-001 — compiler-owned opportunities in pinned Vein Miner

**Status:** Read-only source audit **completed and passed** the pinned-publisher, 28-test, existing H2-first and output-conservation gates on 2026-11-18. This is a lexical/eligibility study, not a new native activation or performance claim.

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

## Completed pinned-source compiler audit — 2026-11-18

The read-only [GitHub Actions audit #44366919067](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44366919067) passed, including **22 existing H2 inventory tests, 6 new compiler audit contracts**, SHA-256 verification of the exact published Vein Miner ZIP (`fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`), and rerunning the original H2 inventory with the new classifier. Original [artifact #14457670398](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44366919067/artifacts/14457670398) includes both original H2 `inventory.json`/`inventory.md` and the new `audit.json`/`audit.md` with per-function evidence. No Minecraft server was booted.

### Source coverage inventory

The exact source archive contains **76 functions**, of which **58 are reachable through the known load/tick function graph**; **55** are in the tick/scheduled set. Those 58 functions contain **635 command lines**; the existing H2 census finds **532 tick lines**.

| Mutually exclusive source-only classification | Command lines | Meaning |
|---|---:|---|
| Lexical fusable or pure-leaf inline candidate | **321** | Source appears to have a recognized leaf family or simple pure-leaf function call; not proved compiled |
| Lexically forked `execute` chain | **102** | Contains a lexical `as`, `at`, `on` or `summon` stage; the existing fuser rejects forked context |
| Recognized parser root, particular shape unproved | **187** | Root is in a known compiler-parser family, but exact Brigadier arguments, modifiers, state and opt-in gates remain unknown |
| Selective macro `function ... with` candidate | **9** | Source-category count only; a tenth `function ... with` was already counted in the forked category |
| Other/vanilla command root | **16** | Includes `tellraw` (8), `random` (5), `time` (2) and `loot` (1) |
| **Total** | **635** | Exactly one category per scanned command |

**Cross-cutting macro call count is 10**, split across **five entity providers and five storage providers**. It intentionally differs from the mutually exclusive 9-line macro category: **one macro invocation also has a forked `execute` wrapper**. Treat `macro provider` as a property of the line, not as a disjoint source category.

The previously tested H2 fuser census gives **266 adjacent tick-path eligible commands in 27 maximal runs**, **295 adjacent eligible commands in 30 runs across the whole reachable graph**, **23.39% lexically forked `execute` lines** (102 of 436), and only **3** simple fake-holder scoreboard adds among all reachable commands. Again: these do **not** prove parser acceptance, actual event execution or whole-server CPU savings.

### Useful locations, but not evidence of hot optimization gaps

Source-based review candidates include:

- `vm:detection/acquire_target`: **145 lexically fusable entries**, alongside the known repeated block-family detection logic. Prior native fusion *already activated* on this kind of workload, and the ten-pair real campaign **failed** its promotion threshold, so these 145 sites are **not** automatically high-value optimization work.
- `vm:detection/verify_mined_stat`: **59 lexically forked `execute` lines**. Prior sample attribution found almost no active tick CPU inside the forked path; do not prioritize fork fusion merely because source occurrence is high.
- `vm:queue/drain`: **two macro `with` calls**, three lexical fusion/inlining candidates, and four recognized parser roots of unproved exact shape. It is an appropriate place to **inspect dynamic parser and macro/cache exposure**, not proof of an unoptimized hotspot.
- `vm:queue/enqueue_diagonals` and `vm:queue/enqueue_faces`: 20 and 6 recognized-function-root but unproved call shapes, predominantly `execute positioned … run function …`. Before any inlining, check actual target leaf qualification, recursion, source modifiers and vanilla call/return semantics.
- `vm:durability/damage_vanilla_pickaxe`: 14 recognized `item` roots in `execute if items … run item modify …`. They are synthetic source candidates with potentially substantial real inventory mutations; no observed runtime frequency or CPU savings claim is supported.

Root-family cross-checks also show **79 `scoreboard` roots whose precise shape is unproved**, **17 `summon`**, **15 `item`**, **14 `kill`**, and **9 `tag` roots in that category.** The latter two are **already explicitly recognized by `StateMachineParser`**, and must not be mislabeled unsupported; the audit's synthetic test includes that regression. Many `scoreboard` examples are `execute store result storage ... run scoreboard players get ...`: the NBT write is semantic work, and static existence does not establish whether a compiled wrapper would be faster.

### Decision gate for the next compiler experiment

**No second compiler optimization is justified by this source audit alone.** The proven win (selective macro argument extraction) is already default-enabled with 11,701/11,701 calls specialized in the recorded native diagnostic; the prior 266 tick fusion candidates are real yet the fused engine failed the real event promotion criterion. The remaining source cases mix legitimate side effects, parser-ineligible modifiers and commands that may rarely execute.

The lowest-risk next **compiler-owned** question is **runtime parser acceptance and fallback counts at specific macro/command lowering boundaries** under the actual default configuration—especially high-frequency macro instantiation, function-local reusable argument shapes and known conditional-store patterns. It must distinguish *a parser recognized the root* from *a compiled command was installed* from *the compiled path actually executed*, and from *a material fraction of event CPU was saved*. Only after a documented high-frequency **miss** and candidate *avoidable* cost should we change compilation logic.

Do not revisit global `DataAccessor`/NBT optimization, broad scheduler replacement or arbitrary regex fusion based solely on these figures. No production compiler gate or method changed in this audit.
