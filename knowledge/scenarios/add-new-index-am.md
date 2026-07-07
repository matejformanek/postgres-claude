---
scenario: add-new-index-am
when_to_use: Brand-new index access method (not just an opclass for an existing AM) — handler function, `IndexAmRoutine`, WAL rmgr, default opclass, `pg_am`/`pg_proc` rows, and SGML.
companion_skills: ["access-method-apis", "wal-and-xlog"]
related_scenarios: ["add-new-operator-class", "add-new-wal-record", "add-new-lwlock-tranche"]
canonical_commit: 7516f525941
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new index access method

## Scope — what's in / out

**In scope:**
- A new built-in index AM living under `src/backend/access/<am>/`
  with `<am>handler` returning a statically-allocated
  `IndexAmRoutine` [verified-by-code `source/src/include/access/amapi.h:233`].
- The required `IndexAmRoutine` callbacks: `ambuild`, `ambuildempty`,
  `aminsert`, `ambulkdelete`, `amvacuumcleanup`, `amcostestimate`,
  `amoptions`, `amvalidate`, `ambeginscan`, `amrescan`, `amendscan`
  — these are asserted non-NULL by `GetIndexAmRoutine`
  [verified-by-code `source/src/backend/access/index/amapi.c:46-56`].
- `pg_am.dat` row (oid_symbol + amhandler + amtype='i') and a
  `pg_proc.dat` row for the handler with
  `prorettype => 'index_am_handler'` [verified-by-code
  `source/src/include/catalog/pg_am.dat`,
  `source/src/include/catalog/pg_proc.dat:934-937`].
- A new WAL resource manager: `PG_RMGR(RM_<AM>_ID, ...)` line in
  `rmgrlist.h` (appended at the end) + redo/desc/identify/mask
  callbacks + WAL rmgrdesc under `src/backend/access/rmgrdesc/`
  [verified-by-code `source/src/include/access/rmgrlist.h:18-50`].
- A default `pg_opclass` (otherwise `CREATE INDEX USING <am>` cannot
  resolve a default) [verified-by-code
  `source/src/include/catalog/pg_opclass.dat`].
- `amcostestimate` impl + extern decl in `index_selfuncs.h` if the
  estimator lives in `selfuncs.c` (canonical pattern for the six
  built-in AMs) [verified-by-code
  `source/src/include/utils/index_selfuncs.h:25-65`].
- `XLOG_PAGE_MAGIC` bump in `xlog_internal.h` because `rmgrlist.h`
  changed [from-comment `source/src/include/access/rmgrlist.h:24`].
- `CATALOG_VERSION_NO` bump (new `pg_am`/`pg_proc`/`pg_opclass`
  rows).

**Out of scope:**
- Pluggable / contrib-style index AMs that register via
  `CREATE ACCESS METHOD ... HANDLER ...` and a custom rmgr ID — that
  is the `RM_EXPERIMENTAL_ID=128` path, see
  [add-new-extension.md](add-new-extension.md). The shape inside the
  module is the same; this scenario covers the in-tree built-in case.
- Per-opclass strategy/support function rows — see
  [add-new-operator-class.md](add-new-operator-class.md). This
  scenario adds **one** default opclass for the AM to be usable; new
  opclasses for additional types come later.
- New table AM — see [add-new-table-am.md](add-new-table-am.md).

## Pre-flight

- **Companion skills:** load `access-method-apis`,
  `wal-and-xlog`. The former is the `IndexAmRoutine` cookbook; the
  latter covers `XLogInsert` / `XLogRegisterBuffer` / rmgrdesc /
  decode plumbing.
- **Canonical commit:** `7516f525941` — *BRIN: Block Range Indexes*
  (Álvaro Herrera, 2014-11-07). The cleanest historical example: it
  adds a whole `src/backend/access/brin/` subtree, a fresh
  `RM_BRIN_ID`, `pg_am`/`pg_proc`/`pg_opclass` entries, `brin.sgml`,
  regress test, and `brincostestimate` in `selfuncs.c`. Read it
  end-to-end before starting [verified-by-code
  `git show 7516f525941`].
- **Common pitfalls (one-line each):**
  - Forgetting to append (not insert) the `PG_RMGR(...)` line in
    `rmgrlist.h` — reordering changes existing rmgr IDs and breaks
    every existing WAL file [from-comment
    `source/src/include/access/rmgrlist.h:18-24`].
  - Forgetting to bump `XLOG_PAGE_MAGIC` — new WAL is silently read
    by old `pg_waldump` builds.
  - Leaving an `IndexAmRoutine` required callback NULL — fires
    `Assert(routine->amXxx != NULL)` in `GetIndexAmRoutine`
    [verified-by-code `source/src/backend/access/index/amapi.c:46-56`].
  - Missing a default opclass — `CREATE INDEX USING <am>` fails with
    "data type X has no default operator class for access method ..."
    even though the AM exists.

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/backend/access/<am>/<am>.c` | (NEW) Handler function `<am>handler(PG_FUNCTION_ARGS)` returning a `pointer to IndexAmRoutine`; main entry points (`<am>build`, `<am>insert`, `<am>beginscan`, …). Pattern: see `brinhandler` at `source/src/backend/access/brin/brin.c:254` [verified-by-code]. | — | access-method-apis |
| 2 | `src/backend/access/<am>/<am>_xlog.c` | (NEW) `<am>_redo`, `<am>_desc`, `<am>_identify`, `<am>_mask` — the rmgr callbacks named in `rmgrlist.h`. | — | wal-and-xlog |
| 3 | `src/backend/access/<am>/<am>_validate.c` | (NEW) `amvalidate` callback — called by `opclasscmds.c` at `CREATE OPERATOR CLASS` time and by `amvalidate(opclassoid)` SQL function. Required: `GetIndexAmRoutine` does not assert it but `opclasscmds.c` will fail [verified-by-code `source/src/backend/access/index/amapi.c:207-211`]. | — | access-method-apis |
| 4 | `src/backend/access/<am>/Makefile` | (NEW) Standard subdir makefile (mirror `src/backend/access/brin/Makefile`). | — | build-and-run |
| 5 | `src/backend/access/<am>/meson.build` | (NEW) Add `<am>.c`, `<am>_xlog.c`, `<am>_validate.c` to the backend object list. | — | build-and-run |
| 6 | `src/backend/access/<am>/README` | (NEW) On-disk layout, page format, locking discipline — mirror BRIN's `README` [verified-by-code `source/src/backend/access/brin/README`]. | — | — |
| 7 | `src/include/access/<am>.h` | (NEW) Public types (e.g. `<Am>BuildState`, `<Am>ScanOpaque`) + handler proto. | — | access-method-apis |
| 8 | `src/include/access/<am>_xlog.h` | (NEW) `XLOG_<AM>_*` info-byte constants, on-disk struct layouts for WAL records. | — | wal-and-xlog |
| 9 | `src/backend/access/Makefile` | Add `<am>` to `SUBDIRS` [verified-by-code `source/src/backend/access/Makefile:11-15`]. | — | build-and-run |
| 10 | `src/backend/access/meson.build` | Add `subdir('<am>')` [verified-by-code `source/src/backend/access/meson.build`]. | — | build-and-run |
| 11 | `src/include/access/amapi.h` | No edit unless the new AM forces a new `IndexAmRoutine` field — but read it to confirm callback signatures [verified-by-code `source/src/include/access/amapi.h:233-326`]. | [amapi.md](../files/src/include/access/amapi.md) | access-method-apis |
| 12 | `src/include/access/rmgr.h` | No edit — `RM_<AM>_ID` is generated from `rmgrlist.h` via `PG_RMGR(symname,...)` [verified-by-code `source/src/include/access/rmgr.h:22-29`]. Confirm there's a free slot before `RM_MIN_CUSTOM_ID=128`. | [rmgr.h.md](../files/src/include/access/rmgr.h.md) | wal-and-xlog |
| 13 | `src/include/access/rmgrlist.h` | Append `PG_RMGR(RM_<AM>_ID, "<Name>", <am>_redo, <am>_desc, <am>_identify, NULL, NULL, <am>_mask, NULL)` at the END — order defines numeric IDs [verified-by-code `source/src/include/access/rmgrlist.h:18-50`]. | [rmgrlist.h.md](../files/src/include/access/rmgrlist.h.md) | wal-and-xlog |
| 14 | `src/include/access/xlog_internal.h` | Bump `XLOG_PAGE_MAGIC` (e.g. `0xD120` → `0xD121`) — change to `rmgrlist.h` requires this [from-comment `source/src/include/access/rmgrlist.h:24`, verified-by-code `source/src/include/access/xlog_internal.h:35`]. | [xlog_internal.h.md](../files/src/include/access/xlog_internal.h.md) | wal-and-xlog |
| 15 | `src/backend/access/rmgrdesc/<am>desc.c` | (NEW) The frontend-linkable rmgrdesc — `<am>_desc` + `<am>_identify` move here so `pg_waldump` can link them [verified-by-code `source/src/backend/access/rmgrdesc/brindesc.c`]. | — | wal-and-xlog |
| 16 | `src/backend/access/rmgrdesc/meson.build` | Add `<am>desc.c` to `rmgr_desc_sources` [verified-by-code `source/src/backend/access/rmgrdesc/meson.build`]. | — | build-and-run |
| 17 | `src/backend/access/rmgrdesc/Makefile` | Add `<am>desc.o` to OBJS. | — | build-and-run |
| 18 | `src/bin/pg_waldump/rmgrdesc.c` | Add `#include "access/<am>_xlog.h"` so frontend builds resolve the rmgr struct [verified-by-code `source/src/bin/pg_waldump/rmgrdesc.c:11-30`]. | — | wal-and-xlog |
| 19 | `src/include/catalog/pg_am.dat` | New row: `{ oid => '<N>', oid_symbol => '<AM>_AM_OID', descr => '...', amname => '<am>', amhandler => '<am>handler', amtype => 'i' }` [verified-by-code `source/src/include/catalog/pg_am.dat:33-35`]. | [pg_am.h.md](../files/src/include/catalog/pg_am.h.md) | catalog-conventions |
| 20 | `src/include/catalog/pg_proc.dat` | Handler proc row: `proname => '<am>handler', provolatile => 'v', prorettype => 'index_am_handler', proargtypes => 'internal', prosrc => '<am>handler'` [verified-by-code `source/src/include/catalog/pg_proc.dat:934-937`]. | [pg_proc.h.md](../files/src/include/catalog/pg_proc.h.md) | catalog-conventions |
| 21 | `src/include/catalog/pg_opfamily.dat` | (At least one) `{ opfmethod => '<am>', opfname => '<type>_ops' }` row to anchor the default opclass. | [pg_opfamily.h.md](../files/src/include/catalog/pg_opfamily.h.md) | catalog-conventions |
| 22 | `src/include/catalog/pg_opclass.dat` | Default opclass: `{ opcmethod => '<am>', opcname => '<type>_ops', opcfamily => '<am>/<type>_ops', opcintype => '<type>', opcdefault => 't', opckeytype => ... }` [verified-by-code `source/src/include/catalog/pg_opclass.dat:271-280`]. | [pg_opclass.h.md](../files/src/include/catalog/pg_opclass.h.md) | catalog-conventions |
| 23 | `src/include/catalog/pg_amop.dat` | One row per (opfamily, strategy, lefttype, righttype, operator) tuple the default opclass supports. | [pg_amop.h.md](../files/src/include/catalog/pg_amop.h.md) | catalog-conventions |
| 24 | `src/include/catalog/pg_amproc.dat` | One row per support function the AM requires (per `amsupport`). | [pg_amproc.h.md](../files/src/include/catalog/pg_amproc.h.md) | catalog-conventions |
| 25 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` — every new `.dat` row requires this [verified-by-code `source/src/include/catalog/catversion.h`]. | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 26 | `src/backend/utils/adt/selfuncs.c` | (NEW function) `<am>costestimate(PlannerInfo *root, IndexPath *path, ...)` — pattern after `brincostestimate` at line 9027 [verified-by-code `source/src/backend/utils/adt/selfuncs.c:9027`]. Optional: can live in `src/backend/access/<am>/<am>cost.c` (bloom does) but the in-tree six AMs all live in `selfuncs.c`. | [selfuncs.c.md](../files/src/backend/utils/adt/selfuncs.c.md) | executor-and-planner |
| 27 | `src/include/utils/index_selfuncs.h` | `extern` decl for `<am>costestimate` [verified-by-code `source/src/include/utils/index_selfuncs.h:25-65`]. | — | executor-and-planner |
| 28 | `src/include/access/reloptions.h` | Add `RELOPT_KIND_<AM> = (1 << N)` if the AM exposes reloptions [verified-by-code `source/src/include/access/reloptions.h:45-52`]. | [reloptions.h.md](../files/src/include/access/reloptions.h.md) | catalog-conventions |
| 29 | `src/backend/access/common/reloptions.c` | Register the new reloptions kind + any `add_*_reloption` calls in `initialize_reloptions` if `RELOPT_KIND_<AM>` was added [verified-by-code `source/src/backend/access/common/reloptions.c:105,213,376`]. | — | catalog-conventions |
| 30 | `doc/src/sgml/<am>.sgml` | (NEW) Chapter describing the AM, opclasses, examples — mirror `doc/src/sgml/brin.sgml` [verified-by-code `source/doc/src/sgml/brin.sgml`]. | — | — |
| 31 | `doc/src/sgml/filelist.sgml` | `<!ENTITY <am> SYSTEM "<am>.sgml">` [verified-by-code `source/doc/src/sgml/filelist.sgml:93-96`]. | — | — |
| 32 | `doc/src/sgml/postgres.sgml` | `&<am>;` include in the indexes part (mirror `&brin;`) [verified-by-code `source/doc/src/sgml/postgres.sgml:260`]. | — | — |
| 33 | `src/test/regress/sql/<am>.sql` | (NEW) Create-index, simple SELECT exercising the AM's scan path, DROP — mirror `src/test/regress/sql/brin.sql` [verified-by-code `source/src/test/regress/sql/brin.sql`]. | — | testing |
| 34 | `src/test/regress/expected/<am>.out` | (NEW) Matching expected output. | — | testing |
| 35 | `src/test/regress/parallel_schedule` | Add `<am>` to a test group (BRIN sits in the group containing `brin gin gist spgist`) [verified-by-code `source/src/test/regress/parallel_schedule:69`]. | — | testing |
| 36 | `src/bin/psql/tab-complete.in.c` | Add `<am>` to the AM-name completion list (search for `USING gin`-style completions). | — | — |

## Phases — suggested split for `pg-feature-plan`

The planner uses this as §8 starting point. Each phase must leave the
tree buildable.

1. **Phase 1 — skeleton + WAL plumbing.** Files: 1, 2, 7, 8, 4, 5, 9,
   10, 12, 13, 14, 15, 16, 17, 18. Edits: create `<am>.c` with a
   stub `<am>handler` returning an `IndexAmRoutine` whose required
   callbacks each `elog(ERROR, "not implemented")`; wire the rmgr
   plumbing end-to-end. Phase-end check: `meson compile -C
   dev/build-debug` succeeds; `pg_waldump --rmgr=list` shows the
   new rmgr name.
2. **Phase 2 — catalog + handler body + cost estimator.** Files: 19,
   20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 11 (read-only), 3.
   Implement the real `<am>build`, `aminsert`, `ambeginscan`,
   `amgettuple`/`amgetbitmap`, `amendscan`, `ambulkdelete`,
   `amvacuumcleanup`, `amvalidate`, `amcostestimate`. Phase-end
   check: `initdb` (forced by catversion bump) + `CREATE INDEX
   x_idx ON t USING <am> (col)` + a SELECT that uses it.
3. **Phase 3 — tests + docs.** Files: 30, 31, 32, 33, 34, 35, 36.
   Phase-end check: `meson test -C dev/build-debug --suite regress
   --test <am>` green + `meson test -C dev/build-debug --suite
   regress` full pass + `make -C doc/src/sgml` clean.

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`brin-summarize-and-scan`](../idioms/brin-summarize-and-scan.md) | shares files: `src/backend/access/brin/brin.c` |
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`wal-page-format`](../idioms/wal-page-format.md) | direct reference |
| [`wal-record-construction`](../idioms/wal-record-construction.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **`rmgrlist.h` append-only** — inserting in the middle renumbers
  every later rmgr ID and breaks every existing WAL stream
  [from-comment `source/src/include/access/rmgrlist.h:18-24`].
- **Forgot `XLOG_PAGE_MAGIC` bump** — the test cluster comes up
  reading older WAL with the new rmgr-id table, decoding garbage. The
  bump invalidates older WAL deliberately [from-comment
  `source/src/include/access/rmgrlist.h:24`].
- **NULL required callback** — `GetIndexAmRoutine` asserts
  `ambuild`, `ambuildempty`, `aminsert`, `ambulkdelete`,
  `amvacuumcleanup`, `amcostestimate`, `amoptions`, `amvalidate`,
  `ambeginscan`, `amrescan`, `amendscan` are all non-NULL
  [verified-by-code `source/src/backend/access/index/amapi.c:46-56`].
  `amgettuple` AND `amgetbitmap` may both be NULL only if the AM
  truly doesn't scan, but at least one is needed for normal use
  (BRIN sets `amgettuple=NULL` and only supports `amgetbitmap`
  [verified-by-code `source/src/backend/access/brin/brin.c:254-300`,
  inferred from struct init]).
- **`amvalidate` is mandatory for `CREATE OPERATOR CLASS`** — even
  if you only ship one default opclass, the SQL-level `amvalidate()`
  function calls `amroutine->amvalidate` and errors if it's NULL
  [verified-by-code `source/src/backend/access/index/amapi.c:207-211`].
- **Default opclass missing** — `CREATE INDEX USING <am>` without an
  explicit opclass calls `GetDefaultOpClass`. If `opcdefault => 't'`
  isn't set on any opclass for the AM, the user gets "no default
  operator class". You must ship at least one default opclass per
  AM, per type you want indexable [verified-by-code
  `source/src/include/catalog/pg_opclass.dat`].
- **Synchronization traps:**
  - `rmgrlist.h` ↔ `xlog_internal.h` (XLOG_PAGE_MAGIC must bump).
  - `rmgrlist.h` ↔ `src/backend/access/rmgrdesc/<am>desc.c` ↔
    `src/bin/pg_waldump/rmgrdesc.c` include list (frontend link).
  - `pg_am.dat` ↔ `pg_proc.dat` (amhandler name must match a
    `index_am_handler`-returning proc).
  - `pg_opclass.dat` ↔ `pg_amop.dat` ↔ `pg_amproc.dat` (opfamily OID
    must agree across all three).
  - `selfuncs.c` `<am>costestimate` ↔ `index_selfuncs.h` extern.

## Verification (exact test invocations)

```bash
# Full regression — your new test runs as part of the parallel
# group you added it to.
meson test -C dev/build-debug --suite regress

# Just your AM's test, fast feedback loop:
meson test -C dev/build-debug --suite regress --test <am>

# WAL replay sanity (forces redo through your rmgr):
meson test -C dev/build-debug --suite recovery

# pg_waldump links the rmgrdesc correctly:
dev/install-debug/bin/pg_waldump --rmgr=list | grep -i <am>

# Catalog smoke:
psql -c "SELECT amname, amhandler FROM pg_am WHERE amtype='i';"
psql -c "\dAc <am>"
```

New tests this scenario expects to ship:

- `src/test/regress/sql/<am>.sql` + `expected/<am>.out`.
- Optionally a `src/test/modules/test_<am>/` if exercising private
  internals — see [add-new-test-module.md](add-new-test-module.md).

## Cross-refs

- Companion skills: `.claude/skills/access-method-apis/SKILL.md`,
  `.claude/skills/wal-and-xlog/SKILL.md`.
- Related scenarios:
  [add-new-operator-class.md](add-new-operator-class.md) (more
  opclasses for the new AM),
  [add-new-wal-record.md](add-new-wal-record.md) (additional WAL
  record kinds within this AM's rmgr later),
  [add-new-lwlock-tranche.md](add-new-lwlock-tranche.md) (if the AM
  needs a shared bookkeeping latch),
  [add-new-extension.md](add-new-extension.md) (the contrib/bloom
  pluggable variant of this scenario).
- Idioms: `knowledge/idioms/catalog-conventions.md` (`.dat` row
  shape, opclass triple), `knowledge/idioms/wal-record-construction.md`,
  `knowledge/idioms/wal-page-format.md`.
- Subsystems: `knowledge/subsystems/access-heap.md`,
  `knowledge/subsystems/access-nbtree.md` (shape reference),
  `knowledge/subsystems/include-access.md`.
- Issues: `knowledge/issues/access.md`,
  `knowledge/issues/access-rmgrdesc.md`,
  `knowledge/issues/bloom.md` (gotchas in the pluggable example).
- Reference patch (canonical_commit): `git -C source show
  7516f525941` — BRIN.
