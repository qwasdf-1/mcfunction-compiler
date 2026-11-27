# Research

This directory holds maintained research findings. Record the target version,
source revision or artifact fingerprint, observed code path, limits of the
evidence, and follow-up questions. Keep conclusions separate from upstream
claims. Do not include decompiled Mojang source or copied third-party code.

| Review | Source and status |
|---|---|
| [Minecraft 26.3 internals](26.3-internals.md) | Exact official bundle and Loom classfile fingerprints; static review plus a wrapper identity and low-quota runtime prototype. |
| [MCFC](mcfc-audit.md) | Static review of GitLab snapshot `15ca1db`; MC 26.1.2 development branch, not a supported release. |
| [Mercury](mercury-audit.md) | Static review of GitHub snapshot `193d65b`; source targets Minecraft 1.21.4. |
| [Bellows](bellows-audit.md) | Static review of GitHub release `1.1.0`, Bellows 1.1.2 runtime probes, and pinned 1.1.3 follow-up; Lithium+Bellows 1.1.3 passes the native 6×6×6 fixture and screening comparisons, and Lithium+Bellows 1.1.3+Moonrise 1.2.0 passes the selected selector/NBT compatibility matrix. Native Moonrise workload checks remain open; Moonrise 1.2.1 fails Bellows mixin startup. |
| [PERF-010/011 profile evidence](real-world-profile-targets.md) | Pinned 26.3 datapack scenarios, Spark capture method, measured stack outcomes, compatibility findings, and eligible-workload compiler probes. |
| [Tick-heavy datapack candidates](tick-heavy-datapack-candidates.md) | Research shortlist for steady tick, entity-spawn burst, and player-triggered workloads, including exact archive screening, optimizer eligibility, and license limits. |
| [Implementation sanity audit](implementation-sanity-audit-2026-10.md) | Scope, design clarity, current command/backend coverage, and performance results reviewed on 2026-10-28. |
| [Follow-up implementation sanity audit](implementation-sanity-audit-2026-10-29.md) | Updated scope, command coverage, selective macro behavior, and three-stack performance evidence reviewed on 2026-10-29. |
| [Engineering Auditor review](engineering-auditor-review-2026-10-29.md) | Pinned EA v1.5.0 advisory scan, coverage limits, and individual review of production findings. |

[`source-versions.lock`](source-versions.lock) fingerprints Minecraft artifacts
used for bytecode inspection. [`toolchain.lock`](toolchain.lock) records the
project's verified development toolchain. [`reference-sources.lock`](reference-sources.lock)
pins the upstream repositories and revisions used for these reviews. Broader
runtime behavior and the candidate issues identified in the audits remain
unverified.

Versioned plans and their validation matrix live under [`../v1/`](../v1/).

## Compiler studies

[Compiler research record through IR-047](compiler-history.md) indexes the preserved accepted, rejected and descriptive studies. Historical source links are pinned; current runtime claims belong in the maintained reference.

[IR-048 — Context-transforming static function dispatch](compiler-typed-ir-048.md) begins with a native cardinality census; no runtime change or performance claim.
