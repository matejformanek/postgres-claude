# Coverage

One row per durable knowledge artifact. Update via the `memory-keeping` skill.

## Subsystems documented

| Name | Path | Last verified commit | Confidence summary | Open questions |
|---|---|---|---|---|
| storage-buffer | knowledge/subsystems/storage-buffer.md | ef6a95c7c64 | verified=49, from-README=27, from-comment=15, inferred=0, unverified=5 | 6 items, see §9 |
| parser-and-rewrite | knowledge/subsystems/parser-and-rewrite.md | 4b0bf0788b0 | verified=20, from-README=5, from-comment=18, inferred=4, unverified=6 | 6 items, see §9 |

<!--
Row format example:
| storage-buffer | knowledge/subsystems/storage-buffer.md | ef6a95c7c64 | verified=N1, from-README=N2, from-comment=N3, inferred=N4, unverified=N5 | M items, see §9 of doc |
-->

## Glossary

| Name | Path | Last verified commit | Confidence summary | Open questions |
|---|---|---|---|---|
| glossary | knowledge/glossary.md | ef6a95c7c64 | 15 entries, cites carried forward from per-file docs (verified-by-code/from-comment/from-README) with explicit "— via" provenance | grown by pg-corpus-maintainer; next terms: LWLock, MemoryContext, MVCC, PGPROC, redo, rmgr |

## Per-file coverage

Authoritative ledger: `progress/files-examined.md` (one row per examined source file).

- Registry rows: **273** (as of 2026-06-01, source commit `ef6a95c7c64`).
- Per-file docs under `knowledge/files/`: **414**.
- The doc count exceeds the registry-row count because some docs cover headers / dir-level overviews that weren't registered as individual rows. Reconciling this is a follow-up.
