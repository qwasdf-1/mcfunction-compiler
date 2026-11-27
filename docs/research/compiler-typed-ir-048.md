# IR-048 — Context-transforming static function dispatch

**Status:** Phase A (native opportunity census and parsed-stage evidence). Branch `work/compiler-ir048`, based on merged Integration-001 `fa4162181e66cf43faf727d33a918bf5379ad4de` plus documentation-only closeout `696a3340c1f7ba05c43b43de2dd220db8030676e`. No new runtime optimization or default change. No general speedup claim.

## Motivation and historical scope

IR043 handles bare static calls and one to eight pure score predicates, not source-transforming commands. IR045 retains native parsed redirects and deferred ordinary terminals. For IR048, evaluate extending native custom-terminal dispatch orchestration without specializing selector resolution or creating child frames. Do not resurrect IR025/028 compiled fork scheduler or cross-command selector caching.

Frozen IR042 native census, 347 sites and 257,697 entries across 17 functions, fixture SHA256 5977367281d9c0958f5dbc3cabb7d22c65902373f71cf1871893a68d14c820a9. Seven historically reached candidate source sites, all in erb, zero ordinary callbacks (custom terminal counts were not observed):

| Shape | Sites | Historical entry visits |
|---|---:|---:|
| as selector at @s run function static ID | 4 | 1963 |
| one score predicate then as selector at @s | 1 | 601 |
| as selector then one score predicate | 2 | 3 |
| Total | 7 | 2567 |

These are historical source entries, not selected entities, terminal calls, successful child completions, CPU shares or evidence of gains. The as-score-write site with 647,279 callbacks investigated in IR025/028 is excluded. The initial candidate is deliberately small.

## Phase A — exact source join and fresh native fanout

Join all frozen rows to the unchanged SHA-pinned original Blastback archive, verify every source index and historical totals, fail on duplicate exact inputs across the publisher's functions, keep only the three observed command sequences. Source-text recognition is a conservative screen, not parsed admission. Observe original BuildContexts entries, actual ContextChain.runModifier calls and returned collections by parsed node names, and actual immediate CustomCommandExecutor.run invocations in the same native BuildContexts scope. The observer is installed only with the fixture build and FC_IR048_CENSUS=true, with a bounded exact-input allowlist and explicitly opened/closed observation window. No timing, no source/callback/selector edits, no mutations, no persistent entity data. Exact inputs identify unique static publisher sites; macro-generated identical inputs cannot be ruled out by text uniqueness alone. Per-stage outputs are collection cardinalities, not necessarily ultimately admitted sources. Custom-terminal invocations are not child task completions. Preserve zeros, stage-call/return mismatches and failure logs; do not fabricate work for @a when no players exist.

Use the existing IR042 original native restoration event (600-tick bounded window with capture witness, exact final state compared to frozen reference, no pack edits). Report fresh per-site counts separate from historical counts. Production JAR inspection must prove new observer classes and command absent; fixture JAR includes them. Require log begin/end, no invalid scope balance, one row per site and positive overall native entry exposure. Native restoration parity required. No CPU timing in census. If terminal hook or parsed signature fails, correct observer against exact mapped bytecode; do not weaken observation gates.

## Proposed Phase B — narrow immutable context-dispatch plan (not implemented)

Only proceed after actual Phase A exposure and review of exact BuildContexts and ContextChain classfiles, including the custom terminal invocation path. Initial shapes above; ordinary native redirects and parsed terminal CustomCommandExecutor must be preserved with exact node/argument identity and fork metadata. Never reparse selectors or change source entity, world, position, rotation or anchor by hand. Preserve ordered stage cost, empty-source suffix debits, fork limit/error handling, source ordering and actual transformed source, callback and native ExecutionControl/frame. No mid-chain quota gate, no extra ExecuteCommand debit for the custom terminal, no synthetic child call, no direct cursor, no source/selector/target caching, no scope expansion to tags, macros, return, store, custom modifiers or arbitrary chains. Trace/nonempty callbacks/restrictive fork limits must use native fallback before effects as needed. Candidate separate default-off flag, not enabled by validated profile. Compare to merged baseline, not abandoned research runtime.

Required differential: zero/one/many selected entities, ordered score-before/after contexts, empty selection and missing entity, fork-limit boundaries and quota truncation, exact @s identity and transformed position/dimension/rotation witnesses, nested/recursive calls, callback/store/return/trace and errors, reload, opaque declines, all relevant IR043–047 inherited checks. Only after exact semantics and positive actual path evidence, run two-boot same-JVM native/candidate paired CPU on exact-work matched parent twins and native child, diagnostics off, calibrated windows and existing 5% stability/A/A thresholds. Retain all failed attempts. No performance claim from counts alone.

## Launch

[Phase A workflow 46057445324](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/46057445324) launched at `2be66a3eee3f811d89d19d9c177ac72415276416`. Pending build, JAR boundary, publisher-source uniqueness and native event/cardinality verification. No runtime changes; the observer is fixture-only. Main documentation closeout `696a334` passed [CI 46057246678](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/46057246678).

## Phase A first attempt and identity correction

[46057445324](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/46057445324) passed both production and fixture builds/JAR checks. Historical join failed closed at `erb:group/join`: identical text is present elsewhere in the original publisher. No native event or counts were obtained. The exact initial revision is retained via `checkpoint/ir048-first-census` (7870ca17), with test run at 2be66a3. [Failure artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/46057445324/artifacts/15227137406).

Rebased both research commits onto main `6268e5fc3d3e64e8394ad19e83c742375698cb22` (Bellows spelling correction); no overlaps or runtime changes. Supersede the text-uniqueness condition: join by function ID and zero-based index, report identical-text multiplicity, then register each original parsed `BuildContexts.Unbound` entry by object identity in a fixture-only FunctionBuilder return observer (wrapper disabled). Validate exact source and custom terminal at registration; require all seven registrations and exact logged keys before accepting results. Distinct identical-text entries now have independent identities. No command or callback wrapping, no production observer. This is an attribution correction, not a relaxation of the exact source-index gate. No live fanout result until the corrected run qualifies.
