---
scenario: add-new-pg-stat-view
when_to_use: New cumulative or live `pg_stat_*` view exposing pgstat counters, plus its supporting SRF and (if needed) a new `PgStat_Kind`.
companion_skills: ["catalog-conventions"]
related_scenarios: ["add-new-system-view","add-new-builtin-function"]
canonical_commit: 87f61f0c828
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new `pg_stat_*` view

## Scope — what's in / out

**In scope:**
- A new view in `src/backend/catalog/system_views.sql` named `pg_stat_xxx`
  that exposes counters maintained by the cumulative-statistics subsystem
  (`src/backend/utils/activity/pgstat_*.c`).
- The supporting set-returning C function (`pg_stat_get_xxx`) that reads
  shared pgstat state and emits rows.
- Wiring for the **stat kind**: either reusing an existing
  `PgStat_Kind` (most additions) or introducing a brand-new one with
  its own `PgStat_KindInfo` slot, callbacks, and shared/snapshot
  structs.
- Catversion bump + `pg_proc.dat` row + `monitoring.sgml` documentation
  + `rules.out` regression update + targeted `stats.sql` test.
- If the new kind changes on-disk layout, the `PGSTAT_FILE_FORMAT_ID`
  bump in `src/include/pgstat.h`
  [verified-by-code](source/src/include/pgstat.h:216-221).

**Out of scope:**
- Plain system views over ad-hoc backend state (memory contexts, shmem
  allocations) — those go through `add-new-system-view`.
- Per-backend live state surfaced via `pg_stat_activity` — that's a
  column on `PgBackendStatus`; touches `backend_status.c` not the
  cumulative subsystem.
- Wait-event additions — those go through `wait_event_names.txt`
  [verified-by-code](source/src/backend/utils/activity/wait_event_names.txt:1).
- Custom stat kinds shipped by an extension (`pgstat_register_kind`
  from `_PG_init`) — covered conceptually here but the extension
  packaging belongs to `add-new-extension`.
- New columns on an existing `pg_stat_*` view — narrow case, just edit
  the SRF + view + docs + rules.out.

## Pre-flight

- **Companion skills:** load `catalog-conventions`. The `pg_proc.dat`
  row, OID picking, and catversion bump all live there; pgstat-specific
  rules are layered on top.
- **Canonical commit:** `87f61f0c828` — *Add pg_stat_autovacuum_scores
  system view.* Seven-file diff that is the minimal pattern: SRF in the
  subsystem source file (`autovacuum.c`), `pg_proc.dat` row, view in
  `system_views.sql`, `monitoring.sgml` summary + per-view section,
  `catversion.h` bump, `rules.out` update
  [verified-by-code](source/src/backend/catalog/system_views.sql:795).
  Read it before starting; it's the textbook "small addition" shape.
  For the heavier shape — actually adding a new `PgStat_Kind` — read
  any `pgstat_<kind>.c` file end-to-end (the `pgstat_io.c` /
  `pgstat_backend.c` introductions are the cleanest templates).
- **Common pitfalls (one-line each):**
  - Touched a `PgStat_*` shared struct but forgot `PGSTAT_FILE_FORMAT_ID`
    — old stats files load with garbage counters
    [from-comment](source/src/include/pgstat.h:213-220).
  - Two-stage flush surprise: `SELECT` right after `INSERT` shows 0
    until pending → shared flush fires; see
    `knowledge/idioms/pgstat-flush-timing.md`.
  - Forgot `REVOKE` / `GRANT pg_read_all_stats` on a privileged view
    (file-header warning at `system_views.sql:8-11`
    [from-comment](source/src/backend/catalog/system_views.sql:8-11)).
  - Edited `pgstat_kind_builtin_infos[]` but forgot to add the matching
    `PGSTAT_KIND_*` macro in `pgstat_kind.h` — compile error or, worse,
    silent zero-init slot.

## File checklist (the FULL sweep)

The first block is mandatory for any `pg_stat_*` addition. The
"new-kind only" block is required *only if* you are introducing a new
`PgStat_Kind`; skip it for views that read from an existing kind.

### Always required

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/backend/catalog/system_views.sql` | The `CREATE VIEW pg_stat_xxx AS SELECT ... FROM pg_stat_get_xxx() ...` definition. Same parsing rules as any other view (`;\n\n` terminator) [from-comment](source/src/backend/catalog/system_views.sql:13-19). Place near related `pg_stat_*` views (the file is loosely grouped by subject). | — | catalog-conventions |
| 2 | `src/backend/catalog/system_views.sql` (perms) | If the view exposes server-wide / cross-database stats (almost all do), add `REVOKE ALL ON pg_stat_xxx FROM PUBLIC;` and `GRANT SELECT ON pg_stat_xxx TO pg_read_all_stats;`. Same applies to the SRF in `pg_proc.dat` if it needs to be restricted. | — | catalog-conventions |
| 3 | `src/include/catalog/pg_proc.dat` | Row for `pg_stat_get_xxx`. Required: `oid`, `descr`, `proname`, `prorettype => 'record'`, `proretset => 't'`, `prorows`, `provolatile => 's'`, `proparallel => 'r'`, `proargtypes`, `proallargtypes`, `proargmodes`, `proargnames`, `prosrc`. Pattern at `87f61f0c828` diff [verified-by-code](source/src/include/catalog/pg_proc.dat:5673). | [pg_proc.dat.md](../files/src/include/catalog/pg_proc.dat.md) | catalog-conventions |
| 4 | `src/backend/utils/adt/pgstatfuncs.c` (or the subsystem's own `.c` if the SRF lives there, e.g. `autovacuum.c`) | The C SRF that reads the stat. Use `InitMaterializedSRF()` + `pgstat_fetch_stat_*()` helpers per the kind (`pgstat_fetch_stat_dbentry`, `pgstat_fetch_stat_tabentry`, etc.) [verified-by-code](source/src/include/pgstat.h:540-570). For a fixed-kind, call `pgstat_fetch_stat_<kind>()`; for variable-kind, iterate `pg_stat_get_replication_slots`-style. | — | fmgr-and-spi |
| 5 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` — the `.dat` row alone forces this [from-comment](source/src/include/catalog/catversion.h:26-29). | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 6 | `doc/src/sgml/monitoring.sgml` (summary table) | Add a row to `monitoring-stats-views-table` (around `monitoring.sgml:442`) [verified-by-code](source/doc/src/sgml/monitoring.sgml:442) — alphabetical insertion within the table. The `<entry>` cites the view name + a `<link linkend="...">` to its detail section. | — | — |
| 7 | `doc/src/sgml/monitoring.sgml` (detail section) | Add a `<sect2 id="monitoring-pg-stat-xxx-view">` with `<title>`, one-paragraph purpose, and a `<table id="pg-stat-xxx-view">` enumerating columns + types + descriptions. Pattern: `pg_stat_autovacuum_scores` block at `monitoring.sgml:4516-4540+` [verified-by-code](source/doc/src/sgml/monitoring.sgml:4516). | — | — |
| 8 | `src/test/regress/expected/rules.out` | The `rules` regression dumps every system view's `pg_get_viewdef`. Adding any `system_views.sql` view diffs this file by ~15-30 lines in two places (`pg_views` listing + the per-view dump) [verified-by-code](source/src/test/regress/expected/rules.out:1286). | — | testing |
| 9 | `src/test/regress/sql/stats.sql` + `expected/stats.out` | Targeted test: `SELECT pg_stat_reset()` (or the kind-specific reset), do some work, call `pg_stat_force_next_flush()` to flush pending → shared, then `SELECT * FROM pg_stat_xxx` and verify counters [verified-by-code](source/src/include/pgstat.h:569-571). | — | testing |

### Only if introducing a new `PgStat_Kind`

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 10 | `src/include/utils/pgstat_kind.h` | Define `PGSTAT_KIND_XXX` macro (next free slot ≤ `PGSTAT_KIND_BUILTIN_MAX`) [verified-by-code](source/src/include/utils/pgstat_kind.h:20-21,27-35). The slot doubles as an index into `pgstat_kind_builtin_infos[]`. | — | — |
| 11 | `src/include/pgstat.h` | (a) Public structs for the new kind (`PgStat_XxxStats` or `PgStat_StatXxxEntry`) — placed in the "on-disk / in-shmem" section guarded by the `PGSTAT_FILE_FORMAT_ID` warning [from-comment](source/src/include/pgstat.h:213-220). (b) `pgstat_count_xxx()` / `pgstat_report_xxx()` API declarations. (c) `pgstat_fetch_stat_xxx()` declaration. | [pgstat.h.md](../files/src/include/pgstat.h.md) | — |
| 12 | `src/include/pgstat.h` (`PGSTAT_FILE_FORMAT_ID`) | Bump the hex constant — ANY change to a `PgStat_*` shared struct that gets serialized must bump this so a stale on-disk stats file is rejected [verified-by-code](source/src/include/pgstat.h:216-221). | [pgstat.h.md](../files/src/include/pgstat.h.md) | — |
| 13 | `src/include/utils/pgstat_internal.h` | Declare `PgStatShared_Xxx` (shared-hash entry layout) and the per-kind callbacks: `pgstat_xxx_flush_cb`, `pgstat_xxx_reset_*_cb`, optional `pgstat_xxx_snapshot_cb`, `to_serialized_name_cb` / `from_serialized_name_cb` (only for kinds with non-integer object IDs like replslot) [verified-by-code](source/src/include/utils/pgstat_internal.h:231-384). | — | — |
| 14 | `src/backend/utils/activity/pgstat_xxx.c` | (NEW file) Implements the callbacks declared in #13 and the public API declared in #11. Look at `pgstat_database.c` (variable, with dboid keyspace), `pgstat_io.c` (fixed-amount, multi-dimensional), or `pgstat_replslot.c` (variable, with name→OID translation) as templates. | — | — |
| 15 | `src/backend/utils/activity/meson.build` | Add the new `pgstat_xxx.c` to `backend_sources` [verified-by-code](source/src/backend/utils/activity/meson.build:3-22). | — | build-and-run |
| 16 | `src/backend/utils/activity/Makefile` | Add the new `.o` (the autotools build still uses it alongside meson) [verified-by-code](source/src/backend/utils/activity/Makefile:1). | — | build-and-run |
| 17 | `src/backend/utils/activity/pgstat.c` (`pgstat_kind_builtin_infos[]`) | Add the `[PGSTAT_KIND_XXX] = { .name = "xxx", .fixed_amount = …, .shared_size = sizeof(PgStatShared_Xxx), .flush_pending_cb = pgstat_xxx_flush_cb, .reset_*_cb = …, }` entry. The array is indexed by kind ID; pattern is dense block per kind at `pgstat.c:283-505` [verified-by-code](source/src/backend/utils/activity/pgstat.c:283-505). | [pgstat.c.md](../files/src/backend/utils/activity/pgstat.c.md) | — |
| 18 | `src/backend/utils/activity/pgstat_shmem.c` | For **fixed-amount** kinds: register the shared struct in `pgstat_init_entry()` / `StatsShmemInit()` path so its size is included in `PgStat_ShmemControl` layout [verified-by-code](source/src/backend/utils/activity/pgstat_shmem.c:1). Variable kinds use the generic dshash and need no edit here. | [pgstat_shmem.c.md](../files/src/backend/utils/activity/pgstat_shmem.c.md) | — |
| 19 | `src/test/recovery/t/029_stats_restart.pl` | Stats persistence test — if the new kind sets `write_to_file = true`, add a check that counters survive a clean restart and are reset on crash [verified-by-code](source/src/test/recovery/t/029_stats_restart.pl:1). | — | testing |

(Use `—` in the per-file doc column for genuinely-new files.)

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Stat kind plumbing (only if new kind).** Files:
   [10, 11, 12, 13, 14, 15, 16, 17, 18]. Add `PGSTAT_KIND_XXX`,
   define structs in `pgstat.h`, bump `PGSTAT_FILE_FORMAT_ID`, write
   the per-kind `pgstat_xxx.c` with flush/reset/snapshot callbacks,
   wire into `pgstat_kind_builtin_infos[]`, register fixed-amount shmem
   slot if applicable. Phase-end check: `meson compile -C
   dev/build-debug` succeeds; a fresh `initdb` boots; server starts
   without "could not read stats file" warnings.
2. **Phase 2 — SRF + catalog entry.** Files: [3, 4, 5]. Implement
   `pg_stat_get_xxx()` using `pgstat_fetch_stat_xxx()`; add
   `pg_proc.dat` row with a random unused OID in 8000-9999
   [from-readme](source/src/include/catalog/unused_oids:73-78); bump
   catversion. Phase-end check: `duplicate_oids` is silent; rebuild +
   re-initdb + `SELECT pg_stat_get_xxx()` returns sane tuples from
   psql.
3. **Phase 3 — View + permissions + docs.** Files: [1, 2, 6, 7]. Add
   the `CREATE VIEW` and the `monitoring.sgml` summary row + detail
   section. Phase-end check: `meson compile -C dev/build-debug docs`
   builds without unresolved `linkend` warnings; `\d+ pg_stat_xxx`
   shows the view.
4. **Phase 4 — Tests.** Files: [8, 9, optionally 19]. Update
   `rules.out` (it WILL diff because `pg_views` lists the new view);
   add a focused `stats.sql` block that mutates state →
   `pg_stat_force_next_flush()` → `SELECT FROM pg_stat_xxx` →
   `pg_stat_reset()` cleanup. Phase-end check: `meson test -C
   dev/build-debug --suite regress` is green; `--suite recovery` too if
   the kind is persistent.

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`fmgr`](../idioms/fmgr.md) | direct reference |
| [`pgstat-flush-timing`](../idioms/pgstat-flush-timing.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **The two-stage flush.** A backend accumulates counters in
  per-backend pending state and only periodically pushes them to the
  shared dshash (interval = `PGSTAT_MIN_INTERVAL` … `PGSTAT_MAX_INTERVAL`)
  [verified-by-code](source/src/backend/utils/activity/pgstat.c:127-129).
  Tests that immediately `SELECT FROM pg_stat_xxx` after the workload
  must call `pg_stat_force_next_flush()` first or counters will read 0.
  See `knowledge/idioms/pgstat-flush-timing.md`.
- **Forgot `PGSTAT_FILE_FORMAT_ID` bump.** Any byte-layout change to a
  serialized `PgStat_*` struct that isn't reflected in the format ID
  means a running cluster loads the old stats file blindly and reads
  garbage. The header comment is unambiguous
  [from-comment](source/src/include/pgstat.h:213-220).
- **`fixed_amount` vs variable kind confusion.** Fixed kinds (archiver,
  bgwriter, checkpointer, wal, slru, io) have exactly one record and
  live in `PgStat_ShmemControl` slots; variable kinds (database,
  relation, function, replslot, subscription, backend) use a dshash
  keyed by `(dboid, objid)`. Picking the wrong flavor cascades into
  every callback — read `PgStat_KindInfo` field-by-field before
  filling the slot [verified-by-code](source/src/include/utils/pgstat_internal.h:231-384).
- **Missing `accessed_across_databases`.** Variable kinds whose
  snapshot should be visible from *any* connected database (e.g.
  `pg_stat_database`) must set this true; otherwise the snapshot
  excludes entries for the other databases and the view returns an
  empty set when queried from `postgres`
  [verified-by-code](source/src/backend/utils/activity/pgstat.c:288-294).
- **REVOKE on the view ≠ REVOKE on the function.** If the SRF stays
  PUBLIC-executable, an unprivileged user can call
  `pg_stat_get_xxx()` directly and bypass the view's GRANT
  [from-comment](source/src/backend/catalog/system_views.sql:8-11).
- **Forgot to add to `meson.build` AND `Makefile`.** Both build systems
  ship; a missing entry in either causes link errors in the corresponding
  CI run [verified-by-code](source/src/backend/utils/activity/meson.build:3-22).
- **Synchronization traps** (sibling files that must change together):
  - `pgstat_kind.h` `PGSTAT_KIND_XXX` macro ↔ `pgstat.c`
    `pgstat_kind_builtin_infos[]` slot (the array is indexed by the
    macro; mismatch = silent zero-init).
  - `pgstat.h` struct layout change ↔ `PGSTAT_FILE_FORMAT_ID` bump.
  - `pg_proc.dat` SRF row ↔ `system_views.sql` view body (column count
    + types must match; mismatch surfaces only at `SELECT * FROM
    pg_stat_xxx` runtime).
  - `system_views.sql` ↔ `rules.out` (the `pg_views` dump and
    `pg_get_viewdef` snapshot must both reflect the new view).
  - `monitoring.sgml` summary `view-table` ↔ `<sect2>` detail
    (`<link linkend>` must resolve or `make html` warns).

## Verification (exact test invocations)

```bash
# Catalog hygiene
./src/include/catalog/duplicate_oids                # expect empty
./src/include/catalog/unused_oids | head            # confirm OID free

# Forced re-initdb (catversion + maybe PGSTAT_FILE_FORMAT_ID bump)
meson compile -C dev/build-debug install
rm -rf dev/data-debug && dev/install-debug/bin/initdb -D dev/data-debug

# Core regression scope this scenario exercises
meson test -C dev/build-debug --suite regress --test stats
meson test -C dev/build-debug --suite regress --test rules
meson test -C dev/build-debug --suite regress --test misc_sanity
meson test -C dev/build-debug --suite regress --test opr_sanity

# Stats persistence (only for write_to_file=true kinds)
meson test -C dev/build-debug --suite recovery --test 029_stats_restart
meson test -C dev/build-debug --suite recovery --test 030_stats_cleanup_replica

# Docs build (catches unresolved linkend in monitoring.sgml)
meson compile -C dev/build-debug docs

# Smoke test from psql
dev/install-debug/bin/psql -c "SELECT * FROM pg_stat_xxx LIMIT 5;"
dev/install-debug/bin/psql -c "SELECT pg_stat_reset(); SELECT pg_stat_force_next_flush();"

# Full check-world before mailing the patch
meson test -C dev/build-debug
```

New stat-specific tests should go into `src/test/regress/sql/stats.sql`
(existing file). A brand-new test file is only warranted for very
large kinds (e.g. `pg_stat_io` got its own test scaffolding in
`stats.sql` ~2024) [verified-by-code](source/src/test/regress/sql/stats.sql:1).

## Cross-refs

- Companion skills:
  - `.claude/skills/catalog-conventions/SKILL.md` — `pg_proc.dat`
    shape, OID picking, catversion mechanics.
  - `.claude/skills/fmgr-and-spi/SKILL.md` — writing the SRF in C.
  - `.claude/skills/testing/SKILL.md` — `rules.out` regen + stats
    flush-timing in tests.
- Related scenarios:
  - `scenarios/add-new-system-view.md` — the generic view-without-stats
    case; this scenario is its pgstat-flavored sibling.
  - `scenarios/add-new-builtin-function.md` — the SRF subset (#3 + #4)
    in isolation.
  - `scenarios/bump-catversion.md` — catversion mechanics.
  - `scenarios/add-new-extension.md` — relevant if the new stat kind
    ships in an extension via `pgstat_register_kind()` rather than the
    built-in table.
- Idioms:
  - `knowledge/idioms/pgstat-flush-timing.md` — pending→shared
    cadence, why tests need `pg_stat_force_next_flush()`.
  - `knowledge/idioms/catalog-conventions.md` — global rules referenced
    by every catalog edit.
  - `knowledge/idioms/fmgr.md` — SRF / `InitMaterializedSRF` patterns.
- Subsystems:
  - `knowledge/subsystems/include-statistics.md` — overview of the
    pgstat subsystem.
  - `knowledge/subsystems/catalog.md` — catalog plumbing.
- Issues:
  - `knowledge/issues/catalog.md` — OID collisions, catversion gaps.
- Reference patch (canonical_commit): `git -C source show 87f61f0c828`.
