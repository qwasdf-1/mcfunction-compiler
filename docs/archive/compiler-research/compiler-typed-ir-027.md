# COMPILER-IR-027 — Real original Blastback completion oracle and complete-volume parity

**Accepted 2026-11-21, correctness only.** Exact unchanged publisher Blastback Hotfix 3
(Minecraft 26.3) is exercised in a new reproducible controlled-stone test
world, first as an original native baseline and then in independent three-JVM
native / plan-only / compiled-fork comparisons.

The full 17×17×17 source volume matches its pre-explosion reference at the
600- and 900-tick post-actor checkpoints in **both independent three-JVM
comparisons**, with original TNT gone and all publisher job/block markers
cleared. The original compiled selector fork is **actually executed**, not
merely admitted to the compiler ledger. This is the stronger same-fixture
restoration oracle needed before an experimental CPU study.

**Do not infer** that the earlier natural-terrain IR026 world was restored,
that a real player's arbitrary-world event is equivalent, that all possible
native entity UUIDs/callbacks were compared, or that any CPU speedup has been
demonstrated. Production flags remain disabled; draft PR #10 is unmerged.

## 1. Why IR026's full template check was confounded

The earlier original TNT fixture filled only the plane at Y=63 with stone and
then cloned the 17³ region containing otherwise natural world terrain. A new
**no-TNT native control**, using that original scene and no Blastback actors,
showed zero block markers and zero restore jobs after 600 datapack ticks **but
failed full-template equality at Y=62 alone** (all other 16 Y slices matched).
This is a fixture-baseline change independent of TNT or compiler execution.

[Native diagnosis run #44944737172](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44944737172).
The pre-event clone matched, but the natural terrain/reference comparison did
not remain stable. The precise block or scheduled-world mechanism causing
that Y=62 drift has not been determined; it must not be assumed to be TNT damage
or a compiler defect.

Source inspection of the unchanged publisher's
`erb:restore/job_tick.mcfunction` shows that `#needs_restore` is reset and
then set while any same-job `erb.block,!erb.verified` marker remains.
The original `erb:restore/finish_job_macro` audits saved blocks, retries
unfinished work, and removes original block/segment/job markers only once the
job is finishable. The old 600-tick snapshots with 20–50 eligible markers
were not a proven completed-restoration state.

Pinned publisher source audit:
[original functions #44944621770](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44944621770).
No publisher function was modified, and no compiler selector index was built.

## 2. Controlled full-stone fixture

The new separate experimental scene is explicitly **not** the IR026
natural-terrain baseline:

1. Force-load the source and reference regions, freeze weather/daylight/random
   ticks as configured, and fill the **entire** source cuboid
   `-4 56 -4` to `12 72 12` with stable stone (4,913 block positions).
2. Place the original five witness blocks (gold, diamond, redstone and
   emerald blocks, plus a stone control) and clone the entire region to
   `64 56 32` through `80 72 48`.
3. Verify all source witnesses and the **complete** original template before
   the event. The SHA-256-pinned, unmodified original Blastback ZIP is copied
   byte-for-byte to each server.
4. In the no-TNT original-native placebo world, observe at least 600 datapack
   ticks and require all 17 vertical slices to remain identical, with zero
   original block/job markers.
5. In the one-TNT original-native world, verify a real tagged TNT actor,
   observe a positive `erb.block` marker population from the original pack,
   and only then allow completion checks. Require TNT disappearance, zero
   saved/block/restore-job markers, zero unresolved/verification/retry markers,
   and full region matching.
6. Record the original publisher `erb:status/collect` counters, verified and
   eligible original marker populations, and per-Y-slice comparisons at each
   checkpoint. The observations are outside any subsequent CPU window.

The source SHA-256 is always

```text
8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90
```

The original `erb:restore/job_tick` fifth command is unchanged, and no
gameplay modifications, alternate selectors or entity indexes are introduced.

## 3. Accepted independently replicated original-native oracle

Two separately run **two-server** baseline experiments (no-TNT and
original-TNT) passed the stable fixture:

- [First native controlled fixture #44944964477](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44944964477):
  no-TNT template matched at 600 ticks, zero markers; TNT scene had no
  outstanding saved/block or restore-job markers and matched the full region
  at 600, 1,200 and 2,400 ticks.
- [Independent original-native validation #44945850016](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44945850016):
  same no-TNT stability, **3,438 original publisher capture markers** observed
  while the real tagged TNT actor was active, TNT gone and complete restoration
  at 600, 1,200 and 2,400 ticks. Additional `erb.unresolved`, retry, verifier,
  fluid/late, job, segment, danger, protected-item and group-member diagnostic
  counts were all zero at the final checkpoints.

The controlled baseline proves a native **event-completion** rather than just a
matching untouched scene. Its events are not work-equal to the old naturally
generated world; no original-world CPU result can be imported.

## 4. Accepted independently replicated native/plan-only/compiled semantic gate

Two separately booted **three-server** experiments each used the original
publisher and controlled stone scene with only the compiler fork flag differing
between plan-only and compiled arms:

- [First original complete-volume matrix #44945900947 attempt 1](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44945900947/attempts/1),
  [evidence artifact 14724100480](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44945900947/artifacts/14724100480).
- [Independent matrix attempt 2](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44945900947/attempts/2),
  [evidence artifact 14723902488](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44945900947/artifacts/14723902488).

| Tested contract (original publisher, 17³ stone fixture) | First three-JVM matrix | Independent three-JVM replication |
| --- | --- | --- |
| Original capture observed, each native / plan / compiled arm | Yes / Yes / Yes | Yes / Yes / Yes |
| Source template matched at 600 and 900 ticks | Yes in all | Yes in all |
| All 17 Y slices matched original reference | Yes in all | Yes in all |
| Block/job/segment/unresolved/retry/verify markers cleared | Yes in all | Yes in all |
| Original one-TNT actor gone | Yes in all | Yes in all |
| Compiled fifth-source-line fork (`C5:1`) admitted | 1 | 1 |
| Actual compiled fork executions | **541** | **541** |
| Live native selected entity sources through compiled fast path | **647,279** | **647,279** |
| Compiled fast-path fallbacks | **0** | **0** |
| Persistent selector/entity cache or new scheduler | None | None |

In both experiments `native_fork_plans=1`, `typed_regions=2`,
`typed_lines=7`; plan-only retained `N5:1`, compiled emitted `C5:1`
at the exact original source position and retained the same `J10:5,J17:2`
neighboring typed regions. The existing direct scheduler still declines the
mixed function.

An **early capture marker count is a sampled population, not a total
execution count**: in the second matrix the native arm saw 3,703 markers at
its sampling instant, while plan-only and compiled saw 3,438. All modes
finished with the same **fully matched full block volume** and no
outstanding markers. Sampling-time variation is recorded, not erased.

The two accepted matrices do not prove arbitrary mod callback/tracing
equivalence or all world blocks outside this 4,913-position region; they
are rigorous full-volume and lifecycle checks for the original, controlled
one-TNT source event.

## 5. Performance stage: separate IR028, no result implied

Only after the independently accepted full-restoration correctness gate is
it reasonable to run a **small exploratory original-publisher CPU pilot**:

- Control A is typed-IR **plan-only**, not plain vanilla. B compiles the
  **same** neighboring scoreboard regions plus the emitted fork. The sole
  treatment switch is `FC_TYPED_IR_COMPILED_FORK`.
- Four new JVMs run in pre-registered order **A1, B1, B2, A2**.
- No compiler diagnostic counters, selector indexes, source tracing,
  ScoreAdd metrics or external profiler are enabled in the measured window.
- Linux `/proc/<pid>/task/<tid>/schedstat` samples **the actual Minecraft
  Server thread** from before one original TNT spawn until 600 actual
  publisher ticks. Host cgroup throttling and runqueue waits are checked;
  any host-quality or >8% A/A-spread failure leaves the result inconclusive.
- Each measured run must observe real publisher capture markers and end with
  zero outstanding block/job markers, original TNT gone and full template
  equality. CPU measurement stops **before** the full post-event status
  diagnostic snapshot.
- Any pilot CPU difference is descriptive, not a general causal claim or
  production promotion. Two servers per variant and a synthetic stable-stone
  scene are not enough to generalize to natural-world Blastback or user
  installations.

IR028 has its own research script and workflow. No IR028 CPU result is implied
by accepting IR027; the original publisher source and compiler design remain
unchanged.

**Disposition:** IR027 is accepted as the **correctness basis**, not a
performance result. Draft PR #10 remains unmerged and production flags off.


## Follow-up — IR028 uninstrumented CPU pilot (2026-11-21)

The subsequent [IR028 completed-event CPU pilot](compiler-typed-ir-028.md)
ran four fresh JVMs in A–B–B–A order, with only the compiled-fork flag
differing between plan-only and compiled arms. All four original TNT events
captured the same 5,769 block markers and fully restored the controlled 17³
template. Server-thread CPU medians were **20.877 ms/tick** plan-only and
**20.849 ms/tick** compiled, an observed **0.137%** reduction against a
**4.804%** A/A spread. Adjacent paired differences had opposite signs.

IR028 is accepted as an uninstrumented exploratory pilot with valid host and
restoration checks, but it does **not** demonstrate a meaningful speedup.
Production remains disabled and PR #10 remains draft/unmerged. The next
investigation is separate JFR stack attribution to determine whether the
compiled path removes enough Brigadier work to justify further optimization.
