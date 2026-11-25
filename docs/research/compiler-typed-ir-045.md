# IR-045 — Native score-store terminal specialization

**Status: implemented; native differential and original publisher accepted; CPU and IR044 regression pending.** Research-only, disabled by default, work/compiler-coverage / draft PR #10.

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
### Native differential — accepted

[Run 45688081984, native artifact 15057162805](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45688081984/artifacts/15057162805), tested commit cfb2065. All 203 snapshots per mode (1,015 total) independently compared from raw ZIP; exact equality across native, old bytecode, interpreted, bytecode and direct-enabled modes. Each enabled arm lowered 17 sites (15 data, 2 scoreboard), entered 394, queued 350, handled 44 modifier errors, zero empty/fallback events. Feature-off counters zero. All expected T layouts and direct exclusions passed. Native full-quota results include storage result 7/success 1, missing data result/success 0, changed value -3, entity x=1/y=64, block-to-marker copy first/unchanged/missing success 1/0/0, copied x=1, nested callback result 7, opaque multi-store and return behavior. Trace and restrictive fork-limit fallbacks not positively exercised; no claim of general mod compatibility.

### Original publisher — accepted

[Artifact 15056808821](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45688081984/artifacts/15056808821). Independently inspected raw ledger and exact frozen native visits. All seven T candidates parsed/admitted: capture/store 5,769, check_captured_position 234, capture/queue 3. D=40 and G=7 sites retained. Within the explicit 15-function erb scope, historical J/D/G/T reaches = 24,665 + 18,703 + 23,078 + 6,006 = 72,452 / 84,758 (85.48%); V=10,614, S=1,091, F=601. The separate generated namespace is not included. Live event completed in 602 ticks, all 17 Y slices and five witnesses, all marker and finish counters zero. Actual T entered/queued 6,006/6,006, zero empty/fallback/errors; D 18,827 entered, 16,185 calls, 2,642 skipped; G 23,078 entered, 230 pass, 22,848 skip. Capture/store layout V1:1,J2:3,D5:1,G6:1,G7:1,G8:1,T9:1,G10:1,D11:1. This is not an event CPU measurement; sampled capture peak differs from earlier events, and the restoration oracle does not establish identical capture cardinality.

### Controlled CPU and inherited regression

Pending.
