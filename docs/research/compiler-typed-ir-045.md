# IR-045 — Native score-store terminal specialization

**Status: implemented; acceptance pending.** Research-only, disabled by default, work/compiler-coverage / draft PR #10.

## Selection
IR044 accepted all five native modes, original publisher restoration and controlled CPU. Remaining archived IR042/044 rows include 5,769 visits at capture/store index 8 (execute store success score @s erb.tmp run data modify entity @s data.saved_nbt set from block ~ ~ ~ {}), 237 at six position extraction sites (three x 78, three x 1). These 6,006 visits are addressable by the proposed narrow store family; the IR042 data/store bucket of 6,547 is an exclusive earlier classification, not all 6,547 necessarily admitted (some sites overlap static region screening or are other operations). The next most frequent plain tag at capture/store has 5,769 visits but is already one native terminal with no redirect; a less promising orchestration target. The high-fanout selector remains separately investigated IR025/028, not justified by callback counts alone.

## Design
T is one original source position. Single parsed execute store result/success score literal fake-holder or @s, followed by native data get entity @s Pos[n] 1, data get storage simple path 1, data modify entity @s simple path set from block ~ ~ ~ {}, or literal scoreboard add (controlled cost isolation). Exact full source/parsed modifier and terminal node identity, ordinary redirect/terminal only, no custom executor, return, chained modifier, selector transformations or generic NBT path expansion. Preserve actual parsed fork bit and original redirect, including native callback creation and composition, resolution of objective/holder, success vs result and errors. Preconstruct native ExecuteCommand and queue it for actual transformed source; no callback synthesized, no direct NBT/score access, no inlined terminal, no persistent state. Trace and restrictive fork limit fall back before debit. Native BuildContexts mapped offsets 130–317 and 519–551, ContinuationTask singleton and ExecuteCommand from IR025. T excludes direct cursor. Flag FC_TYPED_IR_NATIVE_STORE defaults false.

## Fixed gates
- Native five modes, exact observable scoreboard/entity data and tags, native store result/success, data get positive and missing, objective absence, callback composition, block-to-entity copy with changed/unchanged/missing source, no entity, quota truncation, negative opaque layouts, actual T paths. Additional trace/fork-limit evidence desirable, no claim without counters.
- Original SHA-pinned publisher: exact IR042 historical rows joined with actual T ledger, D/G retained, new event final restoration parity and T execution, no CPU claim.
- CPU: 64 native store-to-scoreboard-add entries with 64 increments per call, alternating result/success stores, exact state each window, separate diagnostic preflight, same JVM twins and IR042 fixed calibration, six warmups, two holdouts, two boots, 5% A/A, >=500ms windows. Measures orchestration with native score terminal, not NBT terminal CPU. No gate relaxation.
- IR044 native regression retained.

## Results
Pending.
