# Implementation and Evidence Audit (2026-11)

## Scope reviewed

- Build: `FC_GRADLE_OFFLINE=true ./gradlew classes` (success, Java 25, Fabric 26.3).
- Unit/documentation checks: 14 Python tests pass; doc boundary check passes.
- Runtime semantic check: reduced focused macro probe (`--macro-only --macro-modes mod-free-vanilla selective-macro-arguments --macro-stack fabric --reload-cycles 1`) completed with `vanilla_macro_behavior_parity = true`.
- Benchmark/evidence classification: checked retained JSON campaigns and benchmark protocol decisions.
- Config/documentation comparison against `CompilerConfig.java`.

## Findings

1. **Default enablement still conflicts with AGENTS guidance.**  
   `CompilerConfig` defaults `enabled`, `fused_regions`, and `selective_macros` to `true`. AGENTS requires optimizations to stay disabled until gates close. The repository should either disable these defaults or present confirmatory gate evidence.

2. **Performance promotion is only screening-level.**  
   Retained PERF-011 selective-macro campaigns report `screening_only` with 3-5 pairs and confidence below the declared `0.95` target. README/current-state overstate these as production gains.

3. **Fused-region performance claim lacks a real workload.**  
   No screened datapack has adjacent eligible fused commands. The fused evidence is a static fixture plus compatibility traces, not real-world endpoint gain evidence.

4. **Bytecode claims need scope control.**  
   Opt-in bytecode remains slower than fused on the static fixture. Metaspace no-leak evidence is bounded to the 25-cycle/injected-failure runs and should stay labeled as such.

5. **Configuration key mismatch.**  
   README formerly documented `enable_fused_regions`, `enable_selective_macros`, and `enable_tiered_bytecode`, while `CompilerConfig` uses `fused_regions`, `selective_macros`, and `tiered_bytecode`. Corrected in README, inventory, and configuration reference.

6. **Prototype vs general compiler separation.**  
   Specialized command handlers replace specific parsed Brigadier shapes and retain original command fallback. Inventory title and handler section clarified to avoid implying general compilation.

7. **Selective-macro counter expectation mismatch was corrected.**  
   `scripts/run_runtime_probe.py` expected zero selective-path calls for a wrong-typed storage provider, but supported storage providers enter `buildSelected` for present top-level keys. The expectation was changed based on mode so vanilla remains 0 and selective stays 1.

## Actions taken

- Fixed README configuration keys.
- Updated feature inventory classification and narrow-handler wording.
- Updated configuration reference keys.
- Corrected `run_runtime_probe.py` selective-macro storage counter expectation.
- Added this audit note.
- Ran focused macro runtime probe successfully.
- Ran confirmatory selective-macro sustained benchmarks (`--phase confirmatory --pairs 6`):
  - `lb113`: active tick average median -80.49%, decision `meets_threshold`, confidence 0.96875. Report: `build/benchmarks/PERF-MACRO-SUSTAINED/lb113-confirmatory-6pairs-20261101T012745494207Z/results.json`
  - `lbm113120`: active tick average median -83.22%, decision `meets_threshold`, confidence 0.96875. Report: `build/benchmarks/PERF-MACRO-SUSTAINED/lbm113120-confirmatory-6pairs-20261101T013835628357Z/results.json`
- Real-event 6-pair Vein Miner selective-macro campaigns:
  - Fabric median -22.34%, status complete, decision `meets_threshold`, confidence 0.96875. Report: `build/benchmarks/PERF-011-veinminer/campaigns/vein-6-fabric-selective-macro-6pairs-seed26871028-20261101T020128Z.json`
  - Lithium median -22.06%, status complete, decision `meets_threshold`, confidence 0.96875. Report: `build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lithium-selective-macro-6pairs-seed26871028-20261101T021246Z.json`
  - lb113 repeat (seed 26871031): median -18.34% completion, decision `meets_threshold`; tick average -73.75%, decision `meets_threshold`, 95% confidence. Report: `build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lb113-selective-macro-6pairs-seed26871031-20261101T055249Z.json`
- Real-event 6-pair Vein Miner ScoreAdd campaign:
  - Fabric median -0.88%, status complete, decision `does_not_meet_threshold`. Report: `build/benchmarks/PERF-011-veinminer/campaigns/vein-6-fabric-score-add-6pairs-seed26871028-20261101T015028Z.json`
- Selective macro lifecycle gate:
  - Fabric focused macro probe with 5 reload generations and a forced whole-resource reload failure completed with `vanilla_macro_behavior_parity = true`. Report: `build/reports/runtime-probe/macro-*/macro-*-20261101T050511.server.log` (exact report retained under `build/reports/runtime-probe/macro-*.results.json`).
- Created adjacent-eligible fused prototype workload skeleton:
  - `tests/fixtures/function_compiler_fused_sustained` with a 5000-command contiguous `tick.mcfunction` of `scoreboard players add #fused fc_fused 1`. This is a synthetic adjacent-region fixture, not a real-world datapack; it still needs timing harness integration before publication.
- Pre-release compatibility pass:
  - Focused `vanilla + lbm113120-score-add-on` compatibility probe completed with `compatibility_parity_pass = true`. Report: `build/reports/compatibility-probe/20261101T063220.results.json`.
- Added `docs/reference/stack-aliases.md` so future reports can decode `lb113`, `lbm113`, `lbm113120`, and related aliases exactly.