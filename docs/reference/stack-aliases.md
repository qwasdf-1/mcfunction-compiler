# Fabric Stack Aliases Used in Research Evidence

This page defines the abbreviated Fabric mod-stack labels used in benchmark and
compatibility reports.

| Alias | Lithium | Bellows | Moonrise | Notes |
|---|---|---|---|---|
| `fabric` | No | None | No | Official Minecraft 26.3 reference plus Fabric loader/API. |
| `lithium` | Yes | None | No | Lithium 0.26.2 only. |
| `lb` | Yes | Bellows 1.1.2 | No | Historical Bellows 1.1.2 setup. |
| `lbm` | Yes | Bellows 1.1.2 | Moonrise 1.2.0 | Historical Bellows + Moonrise 1.2.0 setup. |
| `lbm120` | Yes | Bellows 1.1.2 | Moonrise 1.2.0 | Alias retained for explicit Moonrise 1.2.0. |
| `bellows113` | No | Bellows 1.1.3 | No | Bellows 1.1.3 alone. Habitat-related initialization is on the plain Bellows path. |
| `lb113` | Yes | Bellows 1.1.3 | No | Skill award stack used for several selective-macro confirmatory campaigns. |
| `lbm113` | Yes | Bellows 1.1.3 | Moonrise 1.2.0 | Known mixin initialization issue with Moonrise; do not assume startup compatibility. |
| `lbm113120` | Yes | Bellows 1.1.3 | Moonrise 1.2.0 | Preferred compatible Moonrise pairing for the 1.2.0 pin. |

## Selective macro real-event evidence status

| Stack alias | 6-pair result | Decision | Confidence |
|---|---|---|---|
| `fabric` | `-22.34%` | `meets_threshold` | `0.96875` |
| `lithium` | `-22.06%` | `meets_threshold` | `0.96875` |
| `lb113` | `-18.34%` (seed 26871031) | Earlier seed inconclusive. Maintain as "supported but less stable". | `0.96875` on the passing primary metric. |
| `lb113` MSPT metric | `-73.75%` tick average | `meets_threshold` | `0.96875` |

Do not read this as a blanket claim that every Belows stack receives the same gain. The Belows arm had one inconclusive completion campaign and one passing MSPT-first campaign. Use exact report identities when discussing these numbers.