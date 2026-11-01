# Engineering Auditor review — 2026-10-29

**Tool:** Engineering Auditor 1.5.0, release commit
`d014177acf6b3c3cefc425252229d81fbea62150`  
**Profile:** `gating`, report-only  
**Status:** Advisory source review; not an EA gate or a clean-audit claim.

## Reproduction and scope

Run `bash scripts/run_ea_review.sh`. The wrapper verifies the pinned binary's
version and checkout commit, scans the current repository, and writes a local
machine-readable report. It does not use a baseline, suppress findings, or
apply a pass/fail threshold. The shared v1.5.0 worktree path can be overridden
with `FC_ENGINEERING_AUDITOR_ROOT` or `FC_ENGINEERING_AUDITOR_BIN`.

The scan includes Java source, Python and shell tooling, JSON, and Markdown.
It does not establish coverage for Minecraft command semantics, Mixin target
behavior, `.mcfunction` fixtures, or Gradle/Groovy build logic. Those remain
covered by exact-target source review, builds, and runtime probes.

The final scan covered 83 files and reported 87 findings: 1 high, 71 medium,
and 15 low. Five are classified as production-source findings and 82 as
tooling findings. The high finding and all five production findings are
reviewed below. The remaining report is dominated by tooling clone and
complexity signals (45 clone detections and 25 complexity findings); no
documentation-link finding remained after this review's correction.

## Finding review

The scan identified one high-severity structural finding: the runtime probe
orchestrator is 5,516 nonblank lines. This is a maintainability risk for the
test harness, not evidence of a Minecraft correctness defect. Keep the current
runner behavior stable while P0 gates are active; then split the probe by
fixture family behind the same vanilla/off/candidate contract and rerun its
full runtime matrix. Do not suppress the finding.

Five medium findings refer to production-source structure:

| Finding | Review and disposition |
|---|---|
| `FunctionCompilerMod` class complexity | This is the research probe's command registration and diagnostic status surface. Keep it as one entry point while the opt-in prototypes are under investigation; split status reporting from runtime registration before a release design is accepted. No finding indicates incorrect output. |
| `ProbeMetrics` class complexity | It collects counters for the wrapper and disabled research prototypes. Its timer and callback metrics are opt-in; the measurement campaigns keep them off. Keep the common registry until prototype ownership settles, then split only if a production API is retained. |
| `ScoreAddPrototype.compileEntry` return count | Early returns reject unrecognized parse shapes and retain vanilla execution. They are fail-closed eligibility guards. Existing ScoreAdd parity and activation probes cover the supported literal shape and fallback cases; preserve the guards unless a replacement keeps that proof. |
| `SelectiveMacroArgumentPrototype.tryBuild` return count | `null` requests the original Minecraft argument builder for unsupported paths, multiple/non-macro targets, missing custom data, or absent parameters. The focused differential covers selected and fallback cases. Keep these explicit guards. |
| `FunctionCommandMixin.beginFunctionTiming` parameter count | These parameters mirror the pinned Minecraft 26.3 `queueFunctions` injection signature plus Mixin's callback argument. Reducing them would change the injection contract. The timer is disabled by default and is diagnostic-only. |

The scan also reported tooling complexity and duplicated code in profile and
runtime harnesses. Three straightforward findings were corrected during this
review: the temporary port reservation now binds loopback only, Spawn
Animations fixture generation computes its bot count once, and the Vein Miner
runner no longer initializes measurement values that are overwritten before
use. The stale documentation link found during the first scan was corrected.

No baseline or detector suppression was added. Revisit the structural
dispositions before preparing a release, and rerun this review after changing
the affected production files.

## Follow-up scan — 2026-10-29

After the Bellows 1.1.3 runtime and benchmark pass, the pinned wrapper was run
again against the current checkout. It scanned 83 files and reported 87
findings: 1 high, 71 medium, and 15 low. Five findings were classified as
production source and 82 as tooling. The production findings are the five
structural concerns reviewed above; the high finding remains the runtime-probe
orchestrator size. No new production-source finding category appeared. The
machine report is refreshed at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

The scanner currently reports 29 Java, 17 Python, 2 shell, 8 JSON, and 27
Markdown files. This is not coverage of Gradle/Groovy, Mixin contracts,
Minecraft resources, or `.mcfunction` fixtures; those continue to require the
separate review and runtime evidence described above.

## Follow-up scan — PERF-012 runner — 2026-10-29

After adding the sustained selective-macro runner and updating its workload
setup, the pinned v1.5.0 wrapper scanned 86 files and reported 93 findings:
1 high, 75 medium, and 17 low. Five findings are in production Java; 88 are in
tooling. The five production findings match the previously reviewed class
complexity, fail-closed eligibility returns, and Mixin signature findings. No
new production finding category appeared. The local machine report is
`build/reports/engineering-auditor/v1.5.0/report.json`.

The new runner findings are advisory maintainability signals:

| Finding | Review and disposition |
|---|---|
| `prepare_workdir` (6 parameters), `start_server` (7), and `run_arm` (8) exceed the parameter budget | These functions pass the pinned profile, temporary server configuration, and runtime dependencies through the same harness path. A small immutable run-context object could reduce parameter counts, but changing orchestration during active benchmark campaigns would add risk without improving measurement validity. Keep behavior stable through the current gate, then consider this refactor alongside splitting the large runtime probe. |
| `run_arm` (16 branches) and `main` (11 branches) exceed the complexity budget | The branches implement startup cleanup, exact workload validation, opt-in diagnostics, and randomized arm orchestration. They are harness logic, not production paths. Preserve explicit failure handling and add targeted helper boundaries after the active campaigns; do not suppress the findings. |

The existing high structural finding remains `scripts/run_runtime_probe.py` at
5,516 nonblank lines (1,500-line strict threshold). Keep the full P0 runtime
matrix stable, then split it by fixture family behind the existing vanilla,
same-stack compiler-off, and candidate contract and rerun the matrix. The
source scan does not cover Gradle/Groovy, Mixin target behavior, or
`.mcfunction` semantics.

## Follow-up scan — four-generation reload gate — 2026-10-29

After extending the concurrency probe to hold one request while three newer
resource generations publish, the pinned scan covered 86 files and reported
92 findings: 1 high, 74 medium, and 17 low. Five findings remain in production
Java and 87 in tooling; the same five production findings were reviewed above.
No new finding points at the generalized overlapping-reload request helper.
The runner now shares its asynchronous RCON request handling, eliminating one
reported clone, while the existing structural debt remains. The high finding
reports `scripts/run_runtime_probe.py` at 5,584 nonblank lines. Keep the current
P0 matrices reproducible, then split this harness by fixture family and repeat
the full runtime coverage. The refreshed local report is
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — Moonrise 1.2.0 benchmark and documentation sync — 2026-10-29

After recording the Lithium+Bellows 1.1.3+Moonrise 1.2.0 macro compatibility
run, native Vein Miner control, five-pair screen, and current verification
results, the pinned wrapper was run again. It scanned 86 files and reported
92 findings: 1 high, 74 medium, and 17 low. The five production-source
findings are the same structural findings reviewed above; no new production
finding category appeared. The high finding remains the 5,584-nonblank-line
runtime probe orchestrator. The other 87 findings are in tooling. The refreshed
machine report is kept at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

The finding set is unchanged from the four-generation reload review. The
current scan also reports 29 Java, 18 Python, 2 shell, 10 JSON, and 27 Markdown
files. EA does not review Minecraft command semantics, Mixin behavior,
`.mcfunction` fixtures, or Gradle/Groovy build logic; those remain subject to
the project's source, build, runtime, and benchmark gates.

## Follow-up scan — Bellows 1.1.3 compatibility matrix — 2026-10-29

After extending the compatibility runner to Lithium+Bellows 1.1.3+Moonrise
1.2.0 and adding its configuration tests, the pinned v1.5.0 scan covered 87
files and reported 91 findings: 1 high, 73 medium, and 17 low. Five findings
remain in production Java; they are the same reviewed structural concerns, with
no new production finding category. The high finding remains the 5,584-line
runtime-probe orchestrator. The new seven-arm runtime matrix and configuration
test introduced no production finding.

EA reports maintainability findings on `scripts/run_compatibility_probe.py`:
it exceeds the advisory file-size threshold and has clone and branch-complexity
signals. These are harness maintenance concerns, not runtime correctness
findings; preserve the passing mode configuration and parity gate while
planning a later fixture-family split. The scan includes the new Python test
file and still does not cover Gradle/Groovy or Minecraft-specific behavior. The
machine report is refreshed at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — five-request reload gate — 2026-10-29

After extending the runtime probe to hold request A while four newer reloads
publish, the pinned scan again covered 87 files and reported 91 findings:
1 high, 73 medium, and 17 low. The five production-source findings are
unchanged and remain the structural concerns reviewed above. The high tooling
finding now measures `scripts/run_runtime_probe.py` at 5,672 nonblank lines,
78 more than the previous scan. EA also flags its reload-lifecycle function
complexity and clone signals. These findings are harness maintainability debt;
they do not negate the passing runtime evidence, but the added reload logic
should be split into fixture-owned helpers after the active P0 runtime matrix
is stable. Do not suppress the findings.

The run added one end-to-end scenario across mod-free vanilla and all nine Fabric runtime modes.
EA's source scan does not verify that scenario's semantics; the server run and
its asserted vanilla comparisons provide that evidence. The refreshed machine
report remains at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — PERF-011 confirmation and wrong-typed macro case — 2026-10-29

After recording the fixed 23-pair Vein Miner confirmation and adding wrong-typed
and compound/list/int-array entity macro arguments to the vanilla differential
probe, the pinned v1.5.0 scan covered 87 files and reported 91 findings: 1 high,
73 medium, and 17 low. The five production findings are unchanged; the high
tooling finding measures `scripts/run_runtime_probe.py` at 5,825 nonblank lines.
EA continues to flag the runtime probe's lifecycle complexity and clone signals.
These remain tooling maintainability concerns, not findings about Minecraft
behavior. Keep the added P0 cases in the stable parity runner and plan the
previously noted fixture-family split after the active runtime matrix stabilizes.
The scan does not review the `.mcfunction` fixtures or establish their
semantics; the focused 26.3 vanilla/off/candidate server run provides that
evidence.

The refreshed machine report is at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — six-request reload overlap — 2026-10-29

After extending the reload probe to hold A while B through F publish, then
release A last, the pinned v1.5.0 scan covered 87 files and reported 95
findings: 1 high, 77 medium, and 17 low. The five production-source findings
are unchanged. The additional medium findings are in the non-production
source set. The high tooling finding measures
`scripts/run_runtime_probe.py` at 6,105 nonblank lines, up from 5,939 in the
previous scan; EA continues to flag its lifecycle complexity and clone
signals. Keep the six-request P0 parity case while this matrix is active, then
split the runtime harness by fixture family and review the resulting scan.

The scan inventories 29 Java, 19 Python, 2 shell, 10 JSON, and 27 Markdown
files. EA's static scan does not establish reload semantics; the captured
vanilla-plus-nine-mode server comparison provides that evidence. The refreshed
machine report is at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007 isolated callback continuation — 2026-10-29

After adding the `execute if function` return-failure fixture and per-run
continuation-region assertions, the pinned v1.5.0 scan still covered 87 files
and reported 95 findings: 1 high, 77 medium, and 17 low. The five
production-source findings are unchanged. The high tooling finding now
measures `scripts/run_runtime_probe.py` at 6,168 nonblank lines, 63 more than
the previous scan; no new production finding appeared. The additional harness
logic preserves the passing P0 case but increases the already documented
maintenance debt. Split the control-flow fixture family from the runner after
the active matrix stabilizes, then review that scan.

EA's static scan does not establish command behavior. The ten-arm 26.3 runtime
comparison records score 31 and the exact five-event trace in vanilla and all
nine Fabric modes; fused and emitted-bytecode each execute one parent-tail
region. The refreshed machine report is at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — alternate storage-provider macro fallback — 2026-10-29

After adding the wrong-typed storage-provider fallback case to the focused
macro probe, the pinned v1.5.0 scan covered 87 files and reported 92 findings:
1 high, 74 medium, and 17 low. The five production-source findings are
unchanged. The high tooling finding measures
`scripts/run_runtime_probe.py` at 5,885 nonblank lines, up from 5,825 after the
added runtime cases. The additional finding is in the tooling set; no new
production-source finding category appeared. Keep the P0 probe coverage while
the matrix is active, then split the harness by fixture family and review the
resulting scan. This static scan does not establish the storage fallback's
semantics; the Minecraft 26.3 vanilla/off/candidate run provides that evidence.

The current file counts are 29 Java, 19 Python, 2 shell, 10 JSON, and 27
Markdown. The refreshed machine report is at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — nested entity-path fallback — 2026-10-29

After adding the `data.nested` entity-path fallback case, the pinned v1.5.0 scan
still covered 87 files and reported 92 findings: 1 high, 74 medium, and 17 low.
All five production-source findings are unchanged. The high tooling finding
measures `scripts/run_runtime_probe.py` at 5,939 nonblank lines, up from 5,825
in the earlier scan. The added probe case did not change the finding count or
introduce a production-source finding. Continue to preserve the behavior probe
while its P0 matrix is active, then split the harness by fixture family. The
scan does not establish path-selection or fallback semantics; the 26.3
vanilla/off/candidate server runs provide that evidence.

The current file counts remain 29 Java, 19 Python, 2 shell, 10 JSON, and 27
Markdown. The refreshed machine report is at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007 execute-store continuation — 2026-10-29

After adding the `execute store success` child-return-failure case and its
parent-region assertions, the pinned v1.5.0 scan covered 87 files and reported
96 findings: 1 high, 78 medium, and 17 low. The five production-source
findings remain unchanged. The high tooling finding measures
`scripts/run_runtime_probe.py` at 6,215 nonblank lines, 47 more than the prior
scan. No new production-source finding appeared. The runtime result separately
confirms the behavior: all ten arms store success 0, reach score 32, and match
the six-event trace; fused and bytecode each execute one parent continuation
region. The raw scan is retained at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007 execute-store-result continuation — 2026-10-29

After adding the successful `execute store result` callback case, the pinned
v1.5.0 scan covered 87 files and reported 97 findings: 1 high, 78 medium, and
18 low. The five production-source findings remain unchanged. The high tooling
finding measures `scripts/run_runtime_probe.py` at 6,255 nonblank lines, 40
more than the previous scan. A new low tooling finding reports 11 branch
decisions in the runner's `run_case` helper, which now asserts both store
callback types; retain this focused assertion while the matrix is active, then
consider extracting callback fixtures together with the other control-flow
cases. The full ten-arm runtime run confirms score 32, stored result 7, and an
identical six-event trace in every arm; fused and bytecode each execute one
parent continuation region. No new production-source finding appeared. The
raw scan is retained at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007 execute-unless continuation — 2026-10-29

After adding the inverse `execute unless function` child-return-failure case,
the pinned v1.5.0 scan again covered 87 files and reported 97 findings: 1
high, 78 medium, and 18 low. The five production-source findings remain
unchanged, and the existing low finding for `run_case` remains at 11 branch
decisions. The high tooling finding now measures
`scripts/run_runtime_probe.py` at 6,278 nonblank lines, 23 more than the prior
scan; the overall finding count is unchanged. The full ten-arm runtime run
confirms the failed child takes the `+1000` branch, skips the child tail, and
resumes the parent tail at score 1032 with an exact six-event trace. Fused and
bytecode each execute one parent continuation region. Each arm compares 83
debug traces. The raw scan is retained at the ignored local path
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007 failed execute-store-result continuation — 2026-10-29

After adding the failed `execute store result` callback case, the pinned
v1.5.0 scan still covered 87 files and reported 97 findings: 1 high, 78
medium, and 18 low. The five production-source findings and the `run_case`
low finding at 11 branch decisions remain unchanged. The high tooling finding
measures `scripts/run_runtime_probe.py` at 6,303 nonblank lines, 25 more than
the previous scan. No new finding appeared. The full ten-arm runtime run
confirms that the failed child stores result 0, preserves its completed side
effect, discards its pending tail, and resumes the parent tail at score 32
with an exact six-event trace. Fused and bytecode each execute one parent
continuation region; each arm compares 84 debug traces. The raw scan is at
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007 successful execute-store-success continuation — 2026-10-29

After adding the successful `execute store success` callback case, the pinned
v1.5.0 scan still reports 97 findings: 1 high, 78 medium, and 18 low. The five
production-source findings are unchanged. The high tooling finding now measures
`scripts/run_runtime_probe.py` at 6,328 nonblank lines, 25 more than the prior
scan; no new finding appeared. The complete ten-arm runtime run matches vanilla
at score 32 with stored success 1 and the exact six-event trace, although the
child returns numeric result 7. Fused and bytecode each execute one parent
continuation region, and each arm compares 85 debug traces. The raw scan is at
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007 nested execute-store-result return-run continuation — 2026-10-29

After adding the nested `execute store result` with `return run function`
callback case, the pinned v1.5.0 scan still reports 97 findings: 1 high, 78
medium, and 18 low. The five production-source findings are unchanged. The high
tooling finding now measures `scripts/run_runtime_probe.py` at 6,358 nonblank
lines, 30 more than the prior scan; no new finding appeared. The complete
ten-arm runtime run matches vanilla at score 37 with stored result 7 and the
exact eight-event trace, discarding pending tails in both returning frames while
executing the parent continuation once. Fused and bytecode each execute one
parent continuation region, and each arm compares 86 debug traces. The raw scan
is at `build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — CTRL-007/SCORE-010 paired nested execute-store-success return-run continuation — 2026-10-30

After adding the paired nested `execute store success` with `return run function`
callback cases (child returning 7 and child returning failure), the pinned v1.5.0
scan still reports 97 findings: 1 high, 78 medium, and 18 low. The five
production-source findings are unchanged. The high tooling finding now measures
`scripts/run_runtime_probe.py` at 6,418 nonblank lines, 60 more than the prior
scan; no new finding appeared. The complete ten-arm runtime run matches vanilla
at score 37 with stored success 1 (for child return 7) and 0 (for child return fail)
and matching eight-event traces, discarding pending tails in both returning frames
while executing the parent continuation once. Fused and bytecode each execute one
parent continuation region per case, and each arm compares 88 debug traces. The raw
scan is at `build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — MACRO-006 selective macro block provider and alternate entity path fallback — 2026-10-30

After adding wrong-typed block-provider and alternate entity custom-data path (`data.custom_args`)
lifecycle fallback tests, the pinned v1.5.0 scan reports 97 findings: 1 high, 78 medium,
and 18 low. The five production-source findings are unchanged. The high tooling finding now
measures `scripts/run_runtime_probe.py` at 6,538 nonblank lines; no new finding appeared.
The complete ten-arm runtime run matches vanilla state and full debug traces, leaving candidate
fast-path hit counters at zero on fallback paths. The raw scan is at
`build/reports/engineering-auditor/v1.5.0/report.json`.

## Follow-up scan — Documentation pass & tooling local-import cleanup — 2026-10-30

A comprehensive review of the 97 findings identified four fixable `function_local_import`
instances where `argparse` or `re` were imported inside functions rather than at the module
level:
- `scripts/run_entity_datapack_profile.py:124` (`score_value`: local `import re`)
- `scripts/run_score_add_ab.py:882` (`main`: local `import argparse`)
- `scripts/run_spawn_animations_profile.py:186` (`main`: local `import argparse`)
- `scripts/run_veinminer_profile.py:185` (`parse_args`: local `import argparse`)

Promoting these imports to module level resolved all four findings cleanly. The pinned
v1.5.0 scan now reports **93 findings: 1 high, 74 medium, and 18 low**.

The remaining 93 findings break down into:
- **5 Production Findings:**
  - `FunctionCompilerMod` (WMC=42): command registration and diagnostic status formatting. Kept as single entrypoint for opt-in research flags.
  - `ProbeMetrics` (WMC=51): centralized counter/timing registry for wrapper and prototypes. Kept centralized.
  - `ScoreAddPrototype.compileEntry` (10 returns): fail-closed eligibility guards protecting vanilla execution. Kept.
  - `SelectiveMacroArgumentPrototype.tryBuild` (7 returns): fail-closed fallback guards directing unsupported shapes to vanilla argument parser. Kept.
  - `FunctionCommandMixin.beginFunctionTiming` (8 parameters): required Mixin injection signature mirroring pinned Minecraft 26.3 `queueFunctions`.
- **1 High Tooling Finding:** `scripts/run_runtime_probe.py` line count (6,538 nonblank lines). Retained stable while P0 matrix runs are active.
- **87 Tooling Findings:**
  - 47 clone detections (e.g. repeated RCON polling/handshake routines across standalone profile harnesses).
  - 28 function complexity findings (branching in benchmark argument parsers and scenario runners).
  - 10 parameter count findings in harness runner helpers.
  - 2 large file findings (`run_compatibility_probe.py` at 1,381 lines and `run_score_add_ab.py` at 1,084 lines).

The raw scan is at `build/reports/engineering-auditor/v1.5.0/report.json`.

## Interpretation

EA is a static review signal. It does not prove vanilla parity, Mixin
compatibility, scheduler behavior, command quotas, datapack workload integrity,
or performance. Preserve the exact runtime and performance gates in
[`verification.md`](../verification.md) and the shared
[`benchmarking protocol`](../benchmarking.md).
