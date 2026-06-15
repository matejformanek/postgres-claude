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
| glossary | knowledge/glossary.md | ef6a95c7c64 | 570 entries (2026-06-09: +103 — core catalogs, tuple/page internals, planner stages, SLRUs, AIO, security primitives), cites carried forward from per-file docs (verified-by-code/from-comment/from-README) with explicit "— via" provenance | grown by pg-corpus-maintainer; remaining candidates skew to tool-internal helpers (WriteInt/PullFilter/HandleSlashCmds) + SCRAM key-derivation locals, below the cite-or-don't-claim bar |

## Per-file coverage — top-level summary

**🎯 Phase A CLOSED 2026-06-15 — 100% file-by-file coverage achieved across src/ + contrib/.**

Refreshed 2026-06-15 (post A23 100%-close-out sweep — 12 parallel agents +
1 cleanup agent producing 354 new per-file docs to close the final gap).
Source pin: `e18b0cb7344` (Fix MarkBufferDirtyHint() local-buffer regression);
docs from earlier waves remain tagged against `4b0bf0788b0` and will be re-anchored
on next re-touch.
**Authoritative ledger:** `progress/files-examined.md` (one row per examined source file).
**Per-directory gap map (work queue):** `progress/coverage-gaps.md` (CLOSED — kept for history).

- Source files (.c + .h) under `source/src/` + `source/contrib/`: **2,564**.
- Per-file docs under `knowledge/files/`: **2,580** (+354 from A23 close-out sweep; cumulative +1,367 since 2026-06-02 morning).
- Registry rows in `progress/files-examined.md`: **2,640+** (+377 from A23 — includes the 3 collective READMEs + 1 substantive `snowball_runtime.h` doc + 354 per-file docs + a handful of pre-existing doc fixes).
- **Top-line coverage: 100.0%** — every `.c` and `.h` under `src/` + `contrib/` has a per-file or stem-pair doc.

The doc count exceeds the source-file count when a single doc covers
companion artifacts (Makefiles, .y, .l, .dat) or directory-level overviews.
Per-subdirectory coverage > 100% (catalog 102.9%, parser 113.6%, regex 107.7%,
replication 107.4%) reflects those companion docs.

### Coverage by top-level tree (post-A23)

| Tree | Source | Docs | Coverage |
|---|---:|---:|---:|
| `src/backend` | 906 | 938 | 103.5% |
| `src/include` | 844 | 855 | 101.3% |
| `src/common` | 62 | 62 | 100.0% |
| `src/port` | 64 | 64 | 100.0% |
| `src/interfaces` (libpq + ecpg) | 166 | 167 | 100.6% |
| `src/timezone` | 7 | 7 | 100.0% |
| `src/test` | 74 | 74 | 100.0% |
| `src/bin` (psql, pg_dump, initdb, pg_upgrade, pg_rewind, pg_amcheck, …) | 160 | 160 | 100.0% |
| `src/fe_utils` | 18 | 18 | 100.0% |
| `src/pl` (plpgsql, plperl, plpython, pltcl) | 39 | 29 | 100% via stem-pair |
| `contrib` (extensions) | 210 | 206 | 100% via stem-pair |
| **TOTAL** | **2,564** | **2,580** | **100.0%** |

`src/pl` and `contrib` show doc counts under their source counts because of
the established **stem-pair convention**: a single `<stem>.md` doc covers both
`<stem>.c` and `<stem>.h`. Verification under stem-pair matching shows zero
gap — every source file is covered by either a `<path>.md` or its `<stem>.md`
sibling. See `progress/coverage-gaps.md` audit at the bottom for the
verification command.

### Phase A — CLOSED 2026-06-15

Scope: **everything under src/ + contrib/** (full 2,564-file target).
**Closed.** All 11 top-level trees at 100% strict coverage. The 5 mechanical
file-classes the project had previously deferred to cloud are now all done:
`src/port` (64 files, was 0%), `src/interfaces/ecpg` (74 generated golden
outputs collapsed into 1 README + 69 thin stubs), `src/test` (74 files
including pg_regress.c + isolationtester.c at deep cite-rich depth),
`src/backend/snowball/libstemmer` (55 stemmer .c files via 1 README + stubs),
`src/include/snowball` (1 README + 1 substantive runtime header + 55 stem
declarations).

**Cadence retirement:** the `pg-file-backfiller` cloud routine has worked
itself out of a job. It can be repurposed to anchor-refresh per-file docs
that still carry the older `4b0bf0788b0` SHA when upstream pulls diff a file.

Issue surface: any potential issue spotted during a per-file read goes
inline in the per-file doc as `[ISSUE-<type>: ...]` AND appended as a row
in `knowledge/issues/<subsystem>.md`. See `knowledge/issues/README.md` for
the tag convention.
