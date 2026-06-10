# Source anchor refresh — 2026-06-10

**Previous anchor:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (Stamp 19beta1; 2026-06-01 — see `progress/refresh-2026-06-01.md`)
**New anchor:** `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa` (Fix MarkBufferDirtyHint() to not call GetBufferDescriptor() for local buffers; 2026-06-10)
**Master commits absorbed:** 63
**Files changed (.c/.h, excluding `src/test/`):** 55

## Why

The previous anchor was ~10 days stale by 2026-06-10. With 1,908 documented files now in the corpus, ongoing master drift introduces silent cite rot. This refresh:

1. Re-points `source/` (the read-only reference symlink) to current `origin/master`.
2. Bumps the "Source pin" reference in `progress/{STATE,coverage,coverage-gaps}.md` so future foreground sweeps and cloud routines verify against the current master.
3. Leaves per-file docs' "Verified against source pin `4b0bf0788b0`" headers UNCHANGED — those are honest claims about when each doc was last verified. Re-anchoring happens as docs are naturally re-touched.
4. Documents the drift surface here so future sweeps know which docs' cites may now be off-by-N.

## Drift policy

- **Top-line files in `progress/` updated:** `STATE.md`, `coverage.md`, `coverage-gaps.md` all reference `e18b0cb7344` for the new anchor + this file for the drift inventory.
- **Per-file docs:** unchanged. Each doc's `**Verified against source pin <SHA>**` line documents when it was last verified, not what the corpus's current anchor is.
- **`files-examined.md`:** unchanged. Each row's `last-verified commit` column is per-file, not corpus-wide.
- **Cite-rot risk:** for the 55 changed source files below, any `source/.../foo.c:LINE` citation in a per-file doc may have drifted by the listed Δ if the cited line is after the first hunk's start. Sweep agents re-encountering these files should re-verify cites against the new anchor before relying on them.

## Drift inventory (55 files)

| File | Old LOC | New LOC | Δ | First hunk |
|---|---:|---:|---:|---|
| `contrib/pg_buffercache/pg_buffercache_pages.c` | 873 | 924 | +51 | -59,6 +59,8 |
| `contrib/pg_surgery/heap_surgery.c` | 421 | 421 | 0 | -228,8 +228,8 |
| `contrib/spi/refint.c` | 658 | 538 | -120 | -12,7 +12,6 |
| `contrib/xml2/xpath.c` | 888 | 953 | +65 | -147,6 +147,7 |
| `contrib/xml2/xslt_proc.c` | 269 | 276 | +7 | -55,6 +55,7 |
| `src/backend/access/common/tupdesc.c` | 1193 | 1202 | +9 | -517,6 +517,7 |
| `src/backend/catalog/dependency.c` | 3021 | 3040 | +19 | -2165,6 +2165,25 |
| `src/backend/catalog/objectaddress.c` | 6529 | 6618 | +89 | -5850,7 +5850,7 |
| `src/backend/commands/repack_worker.c` | 554 | 536 | -18 | -28,7 +28,7 |
| `src/backend/commands/subscriptioncmds.c` | 3429 | 3431 | +2 | -1748,9 +1748,11 |
| `src/backend/commands/tablecmds.c` | 23907 | 23882 | -25 | -7529,6 +7529,15 |
| `src/backend/executor/execExpr.c` | 5101 | 5068 | -33 | -141,26 +141,6 |
| `src/backend/executor/execTuples.c` | 2609 | 2616 | +7 | -1074,6 +1074,13 |
| `src/backend/executor/nodeModifyTable.c` | 5863 | 5933 | +70 | -199,6 +199,8 |
| `src/backend/jit/llvm/llvmjit.c` | 1285 | 1289 | +4 | -1050,9 +1050,6 |
| `src/backend/optimizer/path/allpaths.c` | 4972 | 4972 | 0 | -4338,7 +4338,7 |
| `src/backend/optimizer/plan/subselect.c` | 3380 | 3382 | +2 | -841,7 +841,9 |
| `src/backend/optimizer/util/clauses.c` | 6345 | 6348 | +3 | -2544,7 +2544,8 |
| `src/backend/optimizer/util/relnode.c` | 3219 | 3245 | +26 | -2845,6 +2845,32 |
| `src/backend/parser/analyze.c` | 4103 | 4099 | -4 | -1549,6 +1549,7 |
| `src/backend/postmaster/datachecksum_state.c` | 1721 | 1721 | 0 | -1005,7 +1005,7 |
| `src/backend/postmaster/syslogger.c` | 1599 | 1618 | +19 | -76,6 +76,12 |
| `src/backend/replication/logical/logicalctl.c` | 637 | 644 | +7 | -256,33 +256,19 |
| `src/backend/replication/logical/slotsync.c` | 2099 | 2099 | 0 | -340,7 +340,7 |
| `src/backend/replication/pgrepack/pgrepack.c` | 287 | 305 | +18 | -13,6 +13,7 |
| `src/backend/replication/slot.c` | 3291 | 3293 | +2 | -788,44 +788,46 |
| `src/backend/rewrite/rewriteGraphTable.c` | 1334 | 1341 | +7 | -714,6 +714,13 |
| `src/backend/storage/buffer/bufmgr.c` | 8967 | 8967 | 0 | -5831,8 +5831,6 |
| `src/backend/tsearch/dict_synonym.c` | 244 | 242 | -2 | -24,7 +24,6 |
| `src/backend/utils/activity/backend_progress.c` | 165 | 163 | -2 | -100,8 +100,6 |
| `src/backend/utils/adt/float.c` | 4321 | 4389 | +68 | -4010,7 +4010,8 |
| `src/backend/utils/adt/pg_locale.c` | 1851 | 1857 | +6 | -1192,7 +1192,13 |
| `src/backend/utils/adt/rowtypes.c` | 2052 | 2052 | 0 | -2030,7 +2030,7 |
| `src/backend/utils/adt/selfuncs.c` | 9240 | 9242 | +2 | -2476,7 +2476,9 |
| `src/backend/utils/adt/tsvector_op.c` | 2896 | 2869 | -27 | -207,17 +207,10 |
| `src/backend/utils/cache/lsyscache.c` | 4030 | 4105 | +75 | -472,6 +472,12 |
| `src/backend/utils/cache/typcache.c` | 3226 | 3219 | -7 | -779,8 +779,9 |
| `src/backend/utils/error/csvlog.c` | 262 | 262 | 0 | -253,7 +253,7 |
| `src/backend/utils/error/elog.c` | 4273 | 4273 | 0 | -3831,7 +3831,7 |
| `src/backend/utils/error/jsonlog.c` | 301 | 301 | 0 | -292,7 +292,7 |
| `src/bin/pg_basebackup/pg_createsubscriber.c` | 2719 | 2714 | -5 | -2381,13 +2381,8 |
| `src/bin/pg_dump/pg_dump.c` | 21102 | 21102 | 0 | -8161,8 +8161,6 |
| `src/bin/psql/common.c` | 2710 | 2750 | +40 | -1499,11 +1499,24 |
| `src/bin/psql/describe.c` | 7699 | 7699 | 0 | -1950,11 +1950,11 |
| `src/bin/scripts/vacuuming.c` | 1050 | 1052 | +2 | -650,13 +650,15 |
| `src/common/unicode_norm.c` | 653 | 653 | 0 | -236,7 +236,7 |
| `src/fe_utils/print.c` | 3974 | 3975 | +1 | -1443,9 +1443,10 |
| `src/include/c.h` | 1513 | 1525 | +12 | -1340,6 +1340,17 |
| `src/include/catalog/catversion.h` | 62 | 62 | 0 | -57,6 +57,6 |
| `src/include/commands/repack_internal.h` | 124 | 122 | -2 | -39,10 +39,8 |
| `src/include/executor/executor.h` | 820 | 818 | -2 | -332,7 +332,6 |
| `src/include/nodes/execnodes.h` | 2813 | 2814 | +1 | -477,7 +477,8 |
| `src/include/postmaster/syslogger.h` | 105 | 106 | +1 | -85,6 +85,7 |
| `src/include/utils/lsyscache.h` | 227 | 229 | +2 | -86,6 +86,8 |
| `src/interfaces/libpq/fe-connect.c` | 8428 | 8440 | +12 | -6050,6 +6050,18 |

## Highest-drift files (Δ ≥ 25 absolute)

1. **`contrib/spi/refint.c`** — Δ -120. Big chunk reverted. **Doc not in corpus** (would have been A14-adjacent; not covered).
2. **`src/backend/catalog/objectaddress.c`** — Δ +89. Property-graph dependency recording (commits `9d8cdcbe0c8`, `4b1e18b0573`).
3. **`src/backend/utils/cache/lsyscache.c`** — Δ +75. lookup helpers grew; affects A7 + dependents.
4. **`src/backend/executor/nodeModifyTable.c`** — Δ +70. FOR PORTION OF inheritance fix (`7d13b03a2e6`).
5. **`src/backend/utils/adt/float.c`** — Δ +68. Container-type hashability fix (`06e94eccfd9`); a `float.h` Phase D site from A15.
6. **`contrib/xml2/xpath.c`** — Δ +65. Not deeply covered yet.
7. **`contrib/pg_buffercache/pg_buffercache_pages.c`** — Δ +51. **A14 deep-read doc — cite drift likely.** `pg_buffercache--1.6--1.7.sql:10-12` NUMA grant cites likely still valid (small file).
8. **`src/bin/psql/common.c`** — Δ +40. psql command dispatch grew (psql pipeline + describe.c qualifications); **A4 deep-read territory**.
9. **`src/backend/executor/execExpr.c`** — Δ -33. Container-type hashability fix removed a deprecated path.
10. **`src/backend/utils/adt/tsvector_op.c`** — Δ -27.

## Cite-rot impact assessment

**LOW drift (most cites still valid):** elog.c, bufmgr.c, heap_surgery.c, pg_dump.c, describe.c, csvlog.c, jsonlog.c — Δ 0 across the board. Per-file docs cited against these files keep working.

**MEDIUM drift (cites past the first hunk drifted):** pg_locale.c (+6), syslogger.c (+19), libpq/fe-connect.c (+12), include/c.h (+12). Cites BEFORE the hunk start are still correct; cites AFTER may be off by the Δ.

**HIGH drift (re-verification needed):** lsyscache.c (+75), pg_buffercache_pages.c (+51), execExpr.c (-33), nodeModifyTable.c (+70), float.c (+68), tsvector_op.c (-27). Per-file docs that cite these files should be re-anchored on next re-touch.

## Operational note

This refresh is a **soft refresh**:
- Top-level pin in `progress/` advances to new anchor.
- Per-file docs and `knowledge/issues/*.md` registers keep their `4b0bf0788b0` tags until naturally re-touched.
- Cloud `pg-quality-auditor` will surface stale cites during routine spot-checks.
- Foreground sweeps that encounter a drift-affected file should bump that doc's `Verified against source pin` to `e18b0cb7344` after re-verifying cites.

A **hard refresh** (rewriting all 1,908 doc headers + every `source/...` cite verification) is not justified at this drift level. Re-verify on touch.

## Cross-references

- Previous refresh: `progress/refresh-2026-06-01.md` (`ef6a95c7c64` → `4b0bf0788b0`, 1 build-system commit, no corpus impact).
- Cloud routine `pg-upstream-watcher` tracks master commits but doesn't bump the anchor — that's a foreground decision (this PR).
- Cloud routine `pg-quality-auditor` will pick up stale cites in routine spot-checks; flag any drift > 50 lines via `ISSUE-cite-drift` for follow-up.
