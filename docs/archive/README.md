# Function Compiler Archive

This directory stores canonical, categorized historical records, superseded
milestone plans, point-in-time sanity scans, and exploratory benchmark logs.

Material in this archive is historical context, not current authority.
Current implementation and verification truth belongs in `docs/reference/`,
`docs/current-state.md`, `docs/architecture.md`, and `docs/verification.md`.

## Archive Categories

| Category | Description & Contents |
|---|---|
| [`audits/`](audits/README.md) | Historical point-in-time sanity scans and audit snapshots. |
| `plans/` | Superseded draft specifications and retired implementation plans. |
| `benchmarks/` | Exploratory or preliminary benchmark logs prior to final calibration. |

## Archiving Rules

1. **Extract current facts first:** Before archiving a document, ensure all
   currently verified behaviors, architectural decisions, and open issues are
   recorded in `docs/reference/` and `docs/current-state.md`.
2. **Narrowest category:** Archive records under their specific subcategory.
3. **No parallel ledgers:** Do not use the archive for active issue tracking or
   open items.
