# Coverage

One row per durable knowledge artifact. Update via the `memory-keeping` skill.

## Subsystems documented

| Name | Path | Last verified commit | Confidence summary | Open questions |
|---|---|---|---|---|
| storage-buffer | knowledge/subsystems/storage-buffer.md | ef6a95c7c64 | verified=49, from-README=27, from-comment=15, inferred=0, unverified=5 | 6 items, see §9 |
| parser-and-rewrite | knowledge/subsystems/parser-and-rewrite.md | 4b0bf0788b0 | verified=20, from-README=5, from-comment=18, inferred=4, unverified=6 | 6 items, see §9 |
| access-nbtree | knowledge/subsystems/access-nbtree.md | 4b0bf0788b0 | verified=42, from-README=13, from-comment=20, inferred=3, unverified=5 | 6 items, see §9 |
| replication | knowledge/subsystems/replication.md | 4b0bf0788b0 | verified=28, from-README=4, from-comment=39, inferred=2, unverified=4 | 6 items, see §9 |
| tcop | knowledge/subsystems/tcop.md | 4b0bf0788b0 | verified=14, from-README=0, from-comment=18, inferred=2, unverified=2 | 4 items, see §9 |

Plus 15 more spine subsystem docs (access-heap, access-transam, storage-lmgr, storage-ipc, utils-mmgr, utils-cache, executor, optimizer, libpq-backend, port, main, foreign, jit, partitioning, headers-wave3) — total **20 subsystem docs**.

<!--
Row format example:
| storage-buffer | knowledge/subsystems/storage-buffer.md | ef6a95c7c64 | verified=N1, from-README=N2, from-comment=N3, inferred=N4, unverified=N5 | M items, see §9 of doc |
-->

## Glossary

| Name | Path | Last verified commit | Confidence summary | Open questions |
|---|---|---|---|---|
| glossary | knowledge/glossary.md | ef6a95c7c64 | 15 entries, cites carried forward from per-file docs (verified-by-code/from-comment/from-README) with explicit "— via" provenance | grown by pg-corpus-maintainer; next terms: LWLock, MemoryContext, MVCC, PGPROC, redo, rmgr |

## Per-file coverage — top-level summary

Refreshed 2026-06-03 (post A5 common sweep), source pin `4b0bf0788b0`.
**Authoritative ledger:** `progress/files-examined.md` (one row per examined source file).
**Per-directory gap map (work queue):** `progress/coverage-gaps.md`.

- Source files (.c + .h) under `source/src/` + `source/contrib/`: **2,564**.
- Per-file docs under `knowledge/files/`: **1,245** (+108 from A5 common sweep; cumulative +328 since 2026-06-02 morning).
- Registry rows in `progress/files-examined.md`: **1,350** (+109).
- **Top-line coverage: ~48.6%** of source files have a per-file doc (up from 44.3%).

The doc count exceeds the registered-file count when a single doc covers
companion artifacts (Makefiles, .y, .l, .dat) or directory-level overviews.
Per-subdirectory coverage > 100% (catalog 102.9%, parser 113.6%, regex 107.7%,
replication 107.4%) reflects those companion docs.

### Coverage by top-level tree

| Tree | Source | Docs | Coverage |
|---|---:|---:|---:|
| `src/backend` | 906 | 644 | 71.1% |
| `src/include` | 844 | 431 | 51.1% |
| `src/common` | 62 | 59 | 95.2% |
| `src/port` | 64 | 0 | 0.0% |
| `src/interfaces` (libpq + ecpg) | 166 | 32 | 19.3% |
| `src/timezone` | 7 | 0 | 0.0% |
| `src/test` | 74 | 0 | 0.0% |
| `src/bin` (psql, pg_dump, initdb, …) | 160 | 79 | 49.4% |
| `src/fe_utils` | 18 | 0 | 0.0% |
| `src/pl` (plpgsql, plperl, plpython, pltcl) | 39 | 0 | 0.0% |
| `contrib` (extensions) | 210 | 0 | 0.0% |
| **TOTAL** | **2,564** | **1,245** | **48.6%** |

### Phase A target (decided 2026-06-02)

Scope: **everything under src/ + contrib/** (full 2,564-file target).
Gap to close: **1,319 files** undocumented (down from 1,427 after A5 common landed 108 docs; cumulative -328 since 2026-06-02 morning's 1,647).
Cadence: hybrid — `pg-file-backfiller` cloud routine grinds breadth nightly;
foreground interactive sweeps accelerate high-value directories
(`utils/`, `libpq-backend`, `replication/`, `executor/`, `bin/`).

Issue surface: any potential issue spotted during a per-file read goes
inline in the per-file doc as `[ISSUE-<type>: ...]` AND appended as a row
in `knowledge/issues/<subsystem>.md`. See `knowledge/issues/README.md` for
the tag convention.
