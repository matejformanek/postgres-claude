# Session — A18 source anchor refresh (hf)

**Date:** 2026-06-10
**Phase:** A — corpus completeness + issue surfacing (maintenance)
**Branch:** `hf_corpus_source_anchor_refresh`

## Scope

**Maintenance operation, not a feature sweep.** Bump the corpus's source pin from `4b0bf0788b0` (2026-06-01, Stamp 19beta1) to `e18b0cb7344` (2026-06-10, MarkBufferDirtyHint local-buffer fix). 63 master commits absorbed; 55 .c/.h files changed outside `src/test/`.

## Method

1. Captured pre-refresh state: anchor `4b0bf0788b0`, master tip in `../postgresql` matched.
2. `git pull --ff-only origin master` in `../postgresql`. New tip: `e18b0cb7344`.
3. Generated drift inventory via `git log --pretty=format:"" --name-only 4b0bf0788b0..origin/master`.
4. Spot-checked LOC deltas + first-hunk locations for the 55 changed files.
5. Updated `progress/{STATE,coverage,coverage-gaps}.md` to advertise new anchor.
6. Wrote `progress/anchor-refresh-2026-06-10.md` with full drift inventory + cite-rot policy.
7. Left per-file docs and `knowledge/issues/*.md` unchanged — re-anchor on next re-touch.

This is a **soft refresh** policy. A hard refresh (re-verifying every cite in all 1,908 docs) is not justified at this drift level — most files have Δ ≤ 10 lines and cites BEFORE the hunk start remain valid.

## Output

**Updated:**
- `progress/coverage.md` — top-line "Source pin" note + new anchor + drift-inventory link.
- `progress/STATE.md` — `Source commit at last verification` line bumped to `e18b0cb7344`.
- `progress/coverage-gaps.md` — top-header pin note + work-queue entry #18 (A18 hf) marked DONE.

**NEW:**
- `progress/anchor-refresh-2026-06-10.md` — drift inventory (55 files) + cite-rot policy + cross-corpus impact assessment.

**Unchanged (by policy):**
- All 1,908 per-file docs under `knowledge/files/`.
- All 38+ subsystem registers under `knowledge/issues/`.
- All 20 subsystem docs under `knowledge/subsystems/`.
- `progress/files-examined.md` (per-row anchors document WHEN each file was examined).

## Drift highlights

**Zero drift (cites still 100% valid):**
- `bufmgr.c`, `elog.c`, `heap_surgery.c`, `pg_dump.c`, `psql/describe.c`
- `csvlog.c`, `jsonlog.c`, `rowtypes.c`, `unicode_norm.c`
- `allpaths.c`, `datachecksum_state.c`, `slotsync.c`, `catversion.h`

**Highest drift (re-verification recommended on touch):**
- `lsyscache.c` (+75)
- `objectaddress.c` (+89)
- `nodeModifyTable.c` (+70)
- `float.c` (+68)
- `xpath.c` (+65)
- `pg_buffercache_pages.c` (+51)
- `psql/common.c` (+40)
- `execExpr.c` (-33)
- `tsvector_op.c` (-27)
- `spi/refint.c` (-120; not deeply covered)

## Major upstream changes in the delta

Inspected the commits to understand what changed semantically:
- **PG18 SQL/PGQ** — `9d8cdcbe0c8` "Record dependencies on graph labels and properties" + `4b1e18b0573` translation marker + property-graph regress tests. **A17 already flagged SQL/PGQ as new attack surface** — A18 confirms ongoing churn.
- **FOR PORTION OF inheritance fix** — `7d13b03a2e6`, A17 nodeModifyTable.h territory.
- **Container-type hashability fix** — `06e94eccfd9`, touches float.c + execExpr.c + clauses.c + lsyscache.c.
- **Logical decoding race fix** — `93a3e6839bf`. A8 logical-rep territory.
- **`pgrepack` direct-use disallowed** — `cd7b204b2df`, A17 repack.h territory.
- **syslogger NULL-pointer dereference fix** — `fb23cc7e81d`. A17 backend_startup.h adjacency.
- **psql describe.c schema qualifications** — `bf5206f0077`. A4 psql secret-scrub adjacency.
- **`pg_createsubscriber` duplicate publication rejection** — `6ce035ffff4`. A8 logical-rep territory.
- **`pg_buffercache_pages()` rowtype verification** — `b70d5672d0c`. **A14 finding territory** (NUMA grant + REVOKE-only gate).
- **EXEC_BACKEND syslogger NULL fix** — touches A17 syslogger.h territory.

**No critical Phase D regressions in the delta.** Most changes are corrective (bug fixes, NULL-pointer guards, race fixes) or feature follow-ups (SQL/PGQ, FOR PORTION OF inheritance, pgrepack hardening).

## Cross-corpus connections

- A17 SQL/PGQ attack surface — confirmed ongoing churn in `objectaddress.c` + `rewriteGraphTable.c` + property-graph tests.
- A14 pg_buffercache NUMA + REVOKE — `pg_buffercache_pages()` rowtype verification was a corrective change to A14 territory.
- A8 logical replication catalog_xmin / output_plugin — `slot.c` + `logicalctl.c` + `slotsync.c` + `subscriptioncmds.c` all touched.
- A17 repack.h — `pgrepack.c` + `repack_worker.c` + `repack_internal.h` corrective patches.

## What this refresh did NOT do

- Did NOT rewrite per-file "Verified against source pin" headers in 1,908 docs.
- Did NOT re-verify cites in registered issues.
- Did NOT update `progress/files-examined.md` per-row anchors.
- Did NOT trigger a full corpus re-validation pass (out of scope for a soft refresh).

A future foreground sweep that touches a drift-affected file should bump that doc's anchor after re-verifying its cites. Cloud `pg-quality-auditor` will surface stale cites during routine spot-checks.

## Position

**Coverage unchanged at 74.4%** (1,908 docs / 2,564 files). This is a maintenance op, not a coverage sweep.

**18 A-operations shipped** (17 sweeps + 1 anchor refresh). The corpus is now anchored 9 days closer to current master.

Next foreground candidates: `src/test` regress framework selectively; OR `src/interfaces/ecpg` (~127 files, low Phase D); OR pivot toward **Phase B** (developer personas).
