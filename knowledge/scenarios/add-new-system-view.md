---
scenario: add-new-system-view
when_to_use: New view in system_views.sql + supporting functions in pg_proc.dat.
companion_skills: ["catalog-conventions"]
related_scenarios: ["add-new-pg-stat-view","add-new-builtin-function","add-new-system-catalog-column"]
canonical_commit: 3e98c0bafb2
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new system view

## Scope — what's in / out

**In scope:**
- Adding a new `pg_*` view to `src/backend/catalog/system_views.sql` that
  exposes server-internal state to SQL.
- The supporting set-returning C function (when needed): `pg_proc.dat`
  entry plus the C implementation that returns tuples via a tuplestore.
- Permissions plumbing (`REVOKE ALL FROM PUBLIC` + `GRANT SELECT TO
  pg_read_all_stats`) for views that expose privileged data.
- Documenting the view under `doc/src/sgml/system-views.sgml` and adding it
  to the `view-table` summary.
- Catversion bump (the `.dat` change forces an initdb).
- Regression-test impact: `rules.out` re-dump diff.

**Out of scope:**
- `pg_stat_*` views backed by the cumulative-statistics system — those go
  through `pgstat_*.c` machinery and have their own scenario
  (`add-new-pg-stat-view`).
- Pure SQL views you create with `CREATE VIEW` at runtime (no BKI / no
  catversion change).
- `information_schema.*` views — those live in
  `src/backend/catalog/information_schema.sql` and follow SQL-standard
  shape conventions.
- New columns on an existing view (touches only `system_views.sql` + the
  underlying function signature; see `add-new-system-catalog-column` for
  catalog columns, or just bump catversion).

## Pre-flight

- **Companion skills:** load `catalog-conventions` — covers OID picking,
  `pg_proc.dat` shape, catversion rules, and the BKI pipeline. Every row
  here either *is* a catalog edit or depends on one.
- **Canonical commit:** `3e98c0bafb2` — *Add pg_backend_memory_contexts
  system view.* Six-file diff that is the textbook example: SRF in
  `mcxt.c`, `pg_proc.dat` row for the function, `system_views.sql` view
  definition, `catalogs.sgml` / `system-views.sgml` documentation,
  `catversion.h` bump, `rules.out` regression update [verified-by-code](source/src/backend/catalog/system_views.sql:709-713).
- **Common pitfalls (one-line each):**
  - Forgot the `REVOKE` on a view that exposes privileged data — anyone
    can `SELECT` it (file header warns about this
    [from-comment](source/src/backend/catalog/system_views.sql:8-11)).
  - Forgot to bump `CATALOG_VERSION_NO` — any developer who pulls your
    branch sees "database files are incompatible with server" at startup
    (see `knowledge/idioms/catalog-conventions.md`).
  - Edited the view body without re-running regression — `rules.out`
    snapshots the `pg_get_viewdef` text of every system view and will
    diff [verified-by-code](source/src/test/regress/expected/rules.out:1286).
  - Missing `proretset => 't'` / `prorows` on the support function — view
    compiles but `SELECT` returns a single composite, not rows.

## File checklist (the FULL sweep)

Every row is mandatory unless explicitly noted "optional". `pg-feature-plan`
will refuse to drop these without a user override.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/backend/catalog/system_views.sql` | The `CREATE VIEW pg_xxx AS SELECT ...` definition. Run once by `initdb` after bootstrap (loaded from `setup_run_file` [verified-by-code](source/src/bin/initdb/initdb.c:3155)). Statement terminator is `;\n\n` — leave a blank line between views [from-comment](source/src/backend/catalog/system_views.sql:13-19). | — | catalog-conventions |
| 2 | `src/backend/catalog/system_views.sql` (perm clause) | If the view exposes privileged data: append `REVOKE ALL ON pg_xxx FROM PUBLIC;` and `GRANT SELECT ON pg_xxx TO pg_read_all_stats;` directly after the `CREATE VIEW`. Pattern repeated for `pg_shmem_allocations`, `pg_backend_memory_contexts`, `pg_dsm_registry_allocations`, `pg_aios` [verified-by-code](source/src/backend/catalog/system_views.sql:691-713,1559). | — | catalog-conventions |
| 3 | `src/include/catalog/pg_proc.dat` | Row for the support function (only if the view needs a C-implemented SRF or scalar fn). Required fields: `oid`, `descr`, `proname`, `prorettype`, `proargtypes`, `prosrc`. For a SRF also set `proretset => 't'`, `prorows`, and `provolatile` / `proparallel` as appropriate. Header warning at file top: also adjust function permissions when the view is privileged — restrict the underlying function in `pg_proc.dat`, not just the view [from-comment](source/src/backend/catalog/system_views.sql:8-11). | — | catalog-conventions |
| 4 | `src/backend/utils/adt/<area>funcs.c` (or `src/backend/utils/mmgr/mcxt.c`, `src/backend/storage/aio/*`, etc.) | The C function the view selects from. Returns tuples via `InitMaterializedSRF()` + `tuplestore_putvalues()`. (NEW file rare — most additions extend an existing source file in the relevant subsystem.) | — | fmgr-and-spi |
| 5 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` to `YYYYMMDDN`. Any `.dat` mutation requires a bump [from-comment](source/src/include/catalog/catversion.h:26-29). | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 6 | `doc/src/sgml/system-views.sgml` | Add a `<sect1>` entry describing the view + a column table (`<sect2>` with `<table>`). Also add a row to the summary `view-table` near the top of the file (alphabetical insertion). Pattern: `pg_backend_memory_contexts` block at [verified-by-code](source/doc/src/sgml/system-views.sgml:773-925). | — | — |
| 7 | `doc/src/sgml/system-views.sgml` (`view-table`) | Add a `<row><entry>` linking to your new view's `<sect1 id="view-pg-xxx">`. The summary table is around [verified-by-code](source/doc/src/sgml/system-views.sgml:67-70) and is alphabetical. | — | — |
| 8 | `src/test/regress/expected/rules.out` | The `rules` test dumps every system view via `SELECT viewname, definition FROM pg_views` and `pg_get_viewdef` [verified-by-code](source/src/test/regress/expected/rules.out:1286,2887). Your new view will appear in two places — re-generate or hand-edit. | — | testing |
| 9 | `src/test/regress/sql/<area>.sql` (+ matching `expected/*.out`) | Add a targeted regression that `SELECT`s from the new view — at minimum a row-count sanity check; if the view exposes typed columns, exercise their formatters. Optional but expected: a privileged-vs-unprivileged variant if the view has a `REVOKE`. | — | testing |
| 10 | `src/test/regress/expected/misc_sanity.out` | `misc_sanity` enforces "no unowned objects in `pg_catalog`" and similar invariants. Usually passes for views created from `system_views.sql` but re-run to confirm. | — | testing |

(Use `—` in the per-file doc column for genuinely-new files; otherwise
the entry should exist in `knowledge/files/` and link.)

## Phases — suggested split for `pg-feature-plan`

The planner will use this as the §8 starting point. Each phase is a
self-contained chunk; the tree must build at the end of each phase.

1. **Phase 1 — Support function (C + catalog entry).** Files: [3, 4].
   Write the SRF in the appropriate `.c` file using `InitMaterializedSRF`
   (pattern in `mcxt.c` `pg_get_backend_memory_contexts`); add the
   `pg_proc.dat` row with a random unused OID in 8000-9999 [from-readme](source/src/include/catalog/unused_oids:73-78).
   Phase-end check: `meson compile -C dev/build-debug` succeeds;
   `./src/include/catalog/duplicate_oids` prints nothing.
2. **Phase 2 — View + permissions + catversion.** Files: [1, 2, 5].
   Add the `CREATE VIEW` (and `REVOKE`/`GRANT` lines if privileged); bump
   `CATALOG_VERSION_NO`. Phase-end check: `initdb` against a fresh data
   directory succeeds; `psql -c '\d+ pg_xxx'` shows the view and the
   `SELECT` returns sane rows.
3. **Phase 3 — Docs.** Files: [6, 7]. Add the `<sect1>` block + a row in
   the summary table. Phase-end check: `meson compile -C dev/build-debug
   docs` (or `cd doc/src/sgml && make html`) builds without warnings.
4. **Phase 4 — Tests.** Files: [8, 9, 10]. Re-run regression; update
   `rules.out` (it will diff because `pg_views` now lists the new view).
   Phase-end check: `meson test -C dev/build-debug --suite regress` is
   green.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/bin` (+2) |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include`, `src/bin` (+1) |
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include`, `src/backend/utils` |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/backend/utils`, `src/test/regress` |
| [`tom-lane`](../personas/tom-lane.md) | `src/backend/utils`, `src/test/regress` |
| [`david-rowley`](../personas/david-rowley.md) | `src/test/regress` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`fmgr`](../idioms/fmgr.md) | direct reference |
| [`memory-context-api-and-dispatch`](../idioms/memory-context-api-and-dispatch.md) | shares files: `src/backend/utils/mmgr/mcxt.c` |
| [`memory-contexts`](../idioms/memory-contexts.md) | shares files: `src/backend/utils/mmgr/mcxt.c` |
| [`security-barrier-views`](../idioms/security-barrier-views.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **`REVOKE ... FROM PUBLIC` on the view is not enough** if the
  underlying support function is still PUBLIC-executable. Set
  `proacl => '{=/foo}'` (or rely on the default-revoke convention by
  picking a `proowner` only the bootstrap superuser holds) in
  `pg_proc.dat` too. The `system_views.sql` file-header comment explicitly
  warns about this [from-comment](source/src/backend/catalog/system_views.sql:8-11).
- **Statement-terminator surprise.** `system_views.sql` is read in
  single-user `-j` mode where the terminator is `;\n\n` (semicolon +
  blank line). A semicolon followed immediately by another non-blank
  line bundles the statements together for error reporting and breaks
  string literals containing `;\n\n` [from-comment](source/src/backend/catalog/system_views.sql:13-19).
- **Missed `rules.out` update.** The `rules` regression test enumerates
  every system view's `pg_get_viewdef` output; adding a view diffs the
  expected file by ~15-30 lines. Regenerate with `meson test --setup
  running --print-errorlogs` and copy the actual output, or hand-edit.
- **Missing catversion bump.** Symptom is a working local cluster (you
  re-initdb'd) but everyone else's existing data directory fails to
  start. See `knowledge/idioms/catalog-conventions.md` §3 [from-comment](source/src/include/catalog/catversion.h:26-29).
- **`InitMaterializedSRF()` mismatch with the view column list.** The
  C function builds a `TupleDesc` from `expectedDesc` (= the view's
  `prorettype` composite type). If your `pg_proc.dat` `prorettype` is a
  bare scalar or `RECORD` without an `OUT` parameter list, the
  call-site fails at execution with "function returning record called in
  context that cannot accept type record". Use `pg_proc.dat`
  `proargmodes => '{o,o,...}'` + `proargnames` for SRFs that return
  named columns (pattern: `pg_get_backend_memory_contexts` in `pg_proc.dat`).
- **OID collision with an in-flight patch.** Two patches grabbing OID
  8473 break CI. Use `./src/include/catalog/unused_oids` to pick a
  random OID in 8000-9999; the committer runs `renumber_oids.pl` before
  push [verified-by-code](source/src/include/catalog/unused_oids:73-78).
- **Synchronization traps** (sibling files that must change together):
  - `system_views.sql` view definition ↔ `pg_proc.dat` function row
    (signature + return type must match the view's `SELECT * FROM
    fn()`).
  - `pg_proc.dat` ↔ `catversion.h` (every `.dat` mutation forces a
    bump).
  - `system-views.sgml` `view-table` summary ↔ the `<sect1>` body
    (both must exist or `make html` warns about unresolved `linkend`).
  - `system_views.sql` ↔ `rules.out` (the regression dump must reflect
    every view defined in the SQL file).

## Verification (exact test invocations)

```bash
# Catalog hygiene before building
./src/include/catalog/duplicate_oids       # expect empty output
./src/include/catalog/unused_oids | head   # confirm your OID is free

# Re-initdb (forced by catversion bump)
meson compile -C dev/build-debug install
rm -rf dev/data-debug && dev/install-debug/bin/initdb -D dev/data-debug

# Regression scope this scenario expects to exercise
meson test -C dev/build-debug --suite regress --test rules
meson test -C dev/build-debug --suite regress --test misc_sanity
meson test -C dev/build-debug --suite regress --test opr_sanity
meson test -C dev/build-debug --suite regress --test sanity_check

# Full check-world to be safe
meson test -C dev/build-debug

# Docs build (catches unresolved linkend)
meson compile -C dev/build-debug docs

# Smoke-test the view by hand
dev/install-debug/bin/psql -c '\d+ pg_xxx'
dev/install-debug/bin/psql -c 'SELECT * FROM pg_xxx LIMIT 5;'
# If REVOKE'd: confirm an unprivileged role sees "permission denied"
dev/install-debug/bin/psql -c "SET ROLE nobody; SELECT * FROM pg_xxx;"
```

If the change adds a brand-new test, name it explicitly here. Typical
new test goes into an existing area file (e.g. `stats.sql`,
`misc_functions.sql`) rather than a new schedule entry.

## Cross-refs

- Companion skills: `.claude/skills/catalog-conventions/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md` (for the SRF C code),
  `.claude/skills/testing/SKILL.md` (rules.out regen).
- Related scenarios:
  - `scenarios/add-new-pg-stat-view.md` — when the new view is backed by
    cumulative statistics (`pgstat_*.c`) rather than ad-hoc state.
  - `scenarios/add-new-builtin-function.md` — the support-function
    subset of this scenario, in isolation.
  - `scenarios/add-new-system-catalog-column.md` — when extending an
    existing catalog rather than projecting one through a view.
  - `scenarios/bump-catversion.md` — catversion mechanics.
- Idioms: `knowledge/idioms/catalog-conventions.md`,
  `knowledge/idioms/fmgr.md`, `knowledge/idioms/security-barrier-views.md`
  (relevant if your view uses `WITH (security_barrier)` like
  `pg_stats`, `pg_stats_ext` [verified-by-code](source/src/backend/catalog/system_views.sql:190,280)).
- Subsystems: `knowledge/subsystems/catalog.md`,
  `knowledge/subsystems/utils.md`.
- Issues: `knowledge/issues/catalog.md` (OID collisions, missing
  catversion bumps, REVOKE/GRANT discipline).
- Reference patch (canonical_commit): `git -C source show 3e98c0bafb2`.
