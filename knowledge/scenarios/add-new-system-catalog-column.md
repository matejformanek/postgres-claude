---
scenario: add-new-system-catalog-column
when_to_use: Adding a new column to an existing `pg_*` system catalog (header `.h` struct field + optional `.dat` seed update + catversion bump + producers/consumers).
companion_skills: ["catalog-conventions"]
related_scenarios: ["bump-catversion","add-new-system-view"]
canonical_commit: 99f8f3fbbc8
last_verified_commit: e18b0cb7344
---

# Scenario — Add a column to an existing system catalog

The canonical example is `99f8f3fbbc8` ("Add relallfrozen to pg_class")
[verified-by-code](source/src/include/catalog/pg_class.h:74) — a 14-file
patch that adds one fixed-width column to `pg_class`. Use that diff as the
reference template; this playbook generalizes the sweep.

## Scope — what's in / out

**In scope:**

- Adding a fixed-width column (Oid / int{16,32,64} / bool / char / NameData)
  to an existing catalog header.
- Adding a varlena / nullable trailing column inside the
  `#ifdef CATALOG_VARLEN` block.
- Updating the catalog's `.dat` seed rows (only catalogs that have a `.dat`
  — `pg_proc`, `pg_type`, `pg_operator`, `pg_amop`, `pg_amproc`, `pg_cast`,
  etc.; `pg_class` and `pg_attribute` are populated by bootstrap C code,
  not `.dat`)
  [from-comment](source/src/include/catalog/pg_attribute.h:6-8).
- All producer sites (`InsertPgClassTuple`-style + relcache `formrdesc` +
  any `CatalogTupleUpdate` callers that touch the row).
- Docs (`catalogs.sgml`), regression coverage that surfaces the column.

**Out of scope:**

- Renaming or removing a catalog column (different change-class; same
  files but different pitfalls around `pg_dump` / `pg_upgrade`).
- Adding a whole new catalog (a much larger sweep — `genbki.pl` declares,
  pinned OIDs, new `_d.h`, syscache decls; planner gap until a dedicated
  scenario exists).
- Adding a column to a *view* (no on-disk layout change) — that's
  [add-new-system-view](add-new-system-view.md).
- Bumping catversion alone — see [bump-catversion](bump-catversion.md).

## Pre-flight

- **Companion skill:** load
  [`catalog-conventions`](../../.claude/skills/catalog-conventions/SKILL.md)
  — the BKI macro vocabulary (`BKI_DEFAULT`, `BKI_LOOKUP`,
  `BKI_FORCE_NOT_NULL`, `CATALOG_VARLEN`) is non-optional here.
- **Canonical commit:** `99f8f3fbbc8` — "Add relallfrozen to pg_class"
  (Plageman, 2025). Read it first: 3-line header diff
  [verified-by-code](source/src/include/catalog/pg_class.h:74) + producer
  edits in `heap.c` + `relcache.c` + the consumer sites in `vacuumlazy.c` /
  `analyze.c` + `relation_stats.c` + 99-line regression update.
- **Common pitfalls (one-line each):**
  - **Wrong field ordering** — fixed-width fields must precede varlena ones;
    varlena/nullable columns belong inside `#ifdef CATALOG_VARLEN`
    [verified-by-code](source/src/include/catalog/genbki.h:148-156),
    [verified-by-code](source/src/include/catalog/pg_class.h:136).
  - **Forgotten catversion bump** — installed clusters silently work; other
    devs' clusters refuse to start
    [from-comment](source/src/include/catalog/catversion.h:7-14).
  - **Producer drift** — `heap.c:InsertPgClassTuple` and
    `relcache.c:formrdesc` must both initialize the new field; otherwise
    nailed-in catalogs read garbage at backend startup.
  - **Default mismatch** — `BKI_DEFAULT(...)` in the header must agree with
    the C initializer in `heap.c`'s `AddNewRelationTuple` (or the
    catalog-specific `Insert...Tuple`).
  - **`Form_pg_X` ABI break** — any out-of-tree extension that does
    `pgcform->newcol = ...` must rebuild; the binary layout has shifted.

## File checklist (the FULL sweep)

Every row is mandatory unless explicitly noted "optional". `pg-feature-plan`
will refuse to drop these without a user override. The canonical-commit
column shows whether `99f8f3fbbc8` touched the file as a sanity anchor.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/pg_<X>.h` | Add the C field inside `CATALOG(...){...}`; pick `BKI_DEFAULT` / `BKI_LOOKUP` / `BKI_FORCE_NOT_NULL` as needed [verified-by-code](source/src/include/catalog/pg_class.h:74) | [pg_class.h.md](../files/src/include/catalog/pg_class.h.md) (or the catalog's own per-file doc) | catalog-conventions |
| 2 | `src/include/catalog/pg_<X>.dat` | Add the new column to every existing seed row if the column has no `BKI_DEFAULT`, or to rows whose value differs from the default. **Skipped by `99f8f3fbbc8`** — `pg_class` has no `.dat` [from-comment](source/src/include/catalog/pg_attribute.h:6-8). Mandatory for `pg_proc`, `pg_type`, `pg_operator`, `pg_cast`, `pg_amop`, `pg_amproc`, `pg_aggregate`, `pg_language`, `pg_opclass`, `pg_opfamily`, `pg_am`, `pg_collation`, `pg_authid`, `pg_database`, `pg_tablespace`, `pg_ts_*`, `pg_namespace`, `pg_range` | varies (e.g. [pg_proc.h.md](../files/src/include/catalog/pg_proc.h.md)) | catalog-conventions |
| 3 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` to today's `YYYYMMDDN`; mandatory because the on-disk row layout changed [from-comment](source/src/include/catalog/catversion.h:26-29), [verified-by-code](source/src/include/catalog/catversion.h:60) | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 4 | `src/include/catalog/indexing.h` | **Only if** the new column joins a unique index. `99f8f3fbbc8` didn't touch it. Otherwise leave alone [verified-by-code](source/src/include/catalog/indexing.h) | [indexing.h.md](../files/src/include/catalog/indexing.h.md) | catalog-conventions |
| 5 | `src/backend/catalog/heap.c` (or the catalog-specific `pg_<X>.c` under `src/backend/catalog/`) | The producer: `InsertPgClassTuple` (or analogue) must set `values[Anum_pg_<X>_newcol - 1]`. The struct initializer in `AddNewRelationTuple` / `Insert<X>Tuple` must also default the new field [verified-by-code](source/src/backend/catalog/heap.c) | [heap.c.md](../files/src/backend/catalog/heap.c.md) | catalog-conventions |
| 6 | `src/backend/utils/cache/relcache.c` | **Only for `pg_class` / `pg_attribute`** — `formrdesc` hard-codes the nailed-in catalogs' tuple field by field; new field must be initialized [verified-by-code](source/src/backend/utils/cache/relcache.c) | [relcache.c.md](../files/src/backend/utils/cache/relcache.c.md) | catalog-conventions |
| 7 | All `CatalogTupleUpdate` / `CatalogTupleInsert` callers that build a tuple for this catalog | Every `values[]` / `nulls[]` / `replaces[]` array sized by `Natts_pg_<X>` needs its bounds re-examined; `replaces[3]` patterns are common and must grow [verified-by-code](source/src/backend/statistics/relation_stats.c) | — | catalog-conventions |
| 8 | `src/backend/utils/cache/syscache.c` | **No edit needed if no new syscache.** If the new column is part of a new unique-index lookup add a `MAKE_SYSCACHE` declaration in the header (item 1) and let `genbki.pl` regenerate `syscache_info.h`/`syscache_ids.h` [verified-by-code](source/src/backend/utils/cache/syscache.c) | [syscache.c.md](../files/src/backend/utils/cache/syscache.c.md) | catalog-conventions |
| 9 | The "producer" subsystem source(s) — wherever the value comes from at runtime (e.g. `src/backend/commands/vacuum.c`, `src/backend/commands/analyze.c`, `src/backend/access/heap/vacuumlazy.c` for `relallfrozen`) | Compute the value and pass it into the `vac_update_relstats` / `index_update_stats` / `Set<X>...` setter [verified-by-code](source/src/backend/commands/vacuum.c) | [analyze.c.md](../files/src/backend/commands/analyze.c.md) (when applicable) | — |
| 10 | The setter signature itself (`src/include/commands/vacuum.h`, `src/include/catalog/index.h`, etc.) | New parameter on `vac_update_relstats` / `index_update_stats` propagates to every caller. ABI break for extensions [verified-by-code](source/src/include/commands/vacuum.h) | — | — |
| 11 | Consumers (planner / executor / statistics / `pg_dump` / FDW) that should now read the new column | Add reads to `Form_pg_<X>->newcol`, statistic-import helpers, `pg_dump` if dumpable, etc. The canonical commit teaches via `relation_stats.c` adding `RELALLFROZEN_ARG` to its `StatsArgInfo[]` [verified-by-code](source/src/backend/statistics/relation_stats.c) | — | — |
| 12 | `doc/src/sgml/catalogs.sgml` | Document the new column inline in the catalog's `<table>` — name, `<type>`, prose. Diff is highly mechanical [verified-by-code](source/doc/src/sgml/catalogs.sgml:2094) | — | — |
| 13 | Regression tests under `src/test/regress/sql/` + matching `expected/` | Any test that selects `*` from the catalog needs its `expected/` updated. `99f8f3fbbc8` updated 99 lines of `stats_import.{sql,out}` because the function signature gained an argument [verified-by-code](source/src/test/regress/sql/stats_import.sql) | — | testing |
| 14 | `src/include/catalog/duplicate_oids` and `./unused_oids` runs (no file edit) | Only relevant when the new column is itself an OID-carrying surface (rare for plain column adds). Always run `duplicate_oids` once as a sanity check [verified-by-code](source/src/include/catalog/duplicate_oids:1-49) | — | catalog-conventions |

(Use `—` in the per-file doc column for genuinely-new files; otherwise the
entry should exist in `knowledge/files/` and link.)

## Phases — suggested split for `pg-feature-plan`

The planner uses this as the §8 starting point. Each phase must leave the
tree buildable. Re-`initdb` between phases when the catversion changes.

1. **Phase 1 — Schema + producer skeleton.** Files: [1, 3, 5, 6, 10, 8].
   Add the struct field, bump catversion, wire producer + relcache
   `formrdesc` + setter signature. Phase-end check: tree builds; `initdb`
   succeeds; `psql -c "\d pg_<X>"` shows the new column with the default
   value; `./duplicate_oids` exits clean. No regression coverage yet.
2. **Phase 2 — Seed data + consumers.** Files: [2, 7, 9, 11]. Update the
   `.dat` rows (catalogs that have one), then teach the producing
   subsystem to compute the real value and consumers to read it.
   Phase-end check: `make check` baseline still green; new behaviour
   observable in `psql` queries against the catalog.
3. **Phase 3 — Tests + docs.** Files: [12, 13]. Add regression coverage
   that surfaces the column (a `SELECT newcol FROM pg_<X>` is the
   minimum); update `catalogs.sgml`. Phase-end check: full
   `meson test --suite regress` green + `make check-world` green.

For a column with no producer logic (purely seed/static), Phases 1+2
collapse into one.



## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`analyze-block-and-reservoir-sampling`](../idioms/analyze-block-and-reservoir-sampling.md) | shares files: `src/backend/commands/analyze.c` |
| [`analyze-mcv-histogram-correlation`](../idioms/analyze-mcv-histogram-correlation.md) | shares files: `src/backend/commands/analyze.c`, `src/include/commands/vacuum.h` |
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`relcache-build`](../idioms/relcache-build.md) | shares files: `src/backend/utils/cache/relcache.c` |
| [`relfilenumber-rewrite`](../idioms/relfilenumber-rewrite.md) | shares files: `src/backend/utils/cache/relcache.c` |
| [`toast-storage-strategies`](../idioms/toast-storage-strategies.md) | shares files: `src/include/catalog/pg_attribute.h` |
| [`vacuum-skip-pages`](../idioms/vacuum-skip-pages.md) | shares files: `src/backend/access/heap/vacuumlazy.c` |
| [`vacuum-truncate-relation`](../idioms/vacuum-truncate-relation.md) | shares files: `src/backend/access/heap/vacuumlazy.c` |
| [`vacuum-two-pass-heap`](../idioms/vacuum-two-pass-heap.md) | shares files: `src/backend/access/heap/vacuumlazy.c` |

<!-- /idioms-invoked:auto -->

## Pitfalls

- **`replaces[N]` array sized by hand.** Patterns like
  `int replaces[3] = {0};` in catalog-update sites must grow when a
  column is added. The canonical commit grew three `[3]` arrays to `[4]`
  in `relation_stats.c`
  [verified-by-code](source/src/backend/statistics/relation_stats.c) —
  if the planner doesn't add this site it will compile but truncate
  updates silently. Grep `replaces\[[0-9]\+\]` in the affected catalog's
  setter sites.
- **Forgotten `relcache.c:formrdesc` init for nailed catalogs.** Only the
  bootstrap catalogs that go through `formrdesc` (`pg_class`,
  `pg_attribute`, `pg_proc`, `pg_type`, plus the indexes on them) need
  this. Symptom: random uninitialized field after backend startup before
  the first relcache build from disk. See
  `relcache.c:formrdesc`
  [verified-by-code](source/src/backend/utils/cache/relcache.c) and
  `relcache.c:RelationSetNewRelfilenumber`
  [verified-by-code](source/src/backend/utils/cache/relcache.c).
- **`Form_pg_<X>` ABI shift.** Any extension that does
  `Form_pg_class form = ...; form->relpages` is now reading from a
  shifted offset if the new column lands *before* `relpages`. Document
  the ABI break in commit message; PG itself rebuilds everything from
  `_d.h` so internal callers stay consistent.
- **Varlena in the fixed section.** Adding a `text` / `oidvector` /
  `pg_node_tree` field outside `#ifdef CATALOG_VARLEN` compiles but
  reading via `Form_pg_X->field` returns garbage because tuple deforming
  doesn't honor the C struct offset for varlenas
  [verified-by-code](source/src/include/catalog/genbki.h:148-156). All
  varlena/nullable trailing columns must live inside the
  `CATALOG_VARLEN` block; access them via `heap_getattr` not the C struct.
- **`BKI_LOOKUP` typo at boot.** If the new column is an OID reference
  and you write `BKI_LOOKUP(pg_namespece)`, `genbki.pl` errors at
  boot-tuple lookup time, not at parse time. Run `make` + check
  `postgres.bki` exists before initdb.
- **Synchronization traps** (sibling files that MUST change together):
  - `pg_<X>.h` field add ↔ `heap.c:Insert<X>Tuple` `values[]` write.
  - `pg_<X>.h` field add ↔ `relcache.c:formrdesc` initializer (nailed
    catalogs only).
  - `pg_<X>.h` field add ↔ `catversion.h` bump (always).
  - Setter signature in `vacuum.h` / `index.h` etc. ↔ every caller in
    `commands/` (the `0, 0,` extra-comma pattern from the canonical
    commit is the smell).
  - Any `.dat` row change ↔ catversion bump (always).

## Verification (exact test invocations)

```bash
# After Phase 1 (rebuild + initdb must succeed)
meson compile -C dev/build-debug
dev/install-debug/bin/initdb -D dev/data-debug --no-sync
dev/install-debug/bin/psql -d postgres -c "\d pg_<X>"   # new col present

# OID-uniqueness sanity (cheap, run after Phase 1)
(cd source/src/include/catalog && ./duplicate_oids)     # expect empty output

# Catalog-shape regression (the most-likely-to-fail suite)
meson test -C dev/build-debug --suite regress --test stats_import
meson test -C dev/build-debug --suite regress --test rules
meson test -C dev/build-debug --suite regress --test psql

# Full sweep before commit
meson test -C dev/build-debug                            # all suites
meson test -C dev/build-debug --suite check-world        # incl. TAP, pg_upgrade
```

If the column has a corresponding `pg_dump`/`pg_upgrade` path, also:

```bash
meson test -C dev/build-debug --suite pg_upgrade
```

If the change adds a brand-new regression test, name it explicitly here.
For the canonical commit the existing test that surfaced the change was
`src/test/regress/sql/stats_import.sql`
[verified-by-code](source/src/test/regress/sql/stats_import.sql) — its
`expected/stats_import.out` grew by 99 lines.

## Cross-refs

- Companion skill:
  [`.claude/skills/catalog-conventions/SKILL.md`](../../.claude/skills/catalog-conventions/SKILL.md).
- Related scenarios:
  - [`bump-catversion`](bump-catversion.md) — the one-line edit that this
    playbook subsumes.
  - [`add-new-system-view`](add-new-system-view.md) — when the surface is
    a view, not an on-disk catalog.
  - [`add-new-builtin-function`](add-new-builtin-function.md) — for the
    sibling "add a row to `pg_proc.dat`" change-class.
- Idioms:
  - [`catalog-conventions`](../idioms/catalog-conventions.md) — BKI
    macros, OID ranges, catversion rules.
  - [`relcache-build`](../idioms/relcache-build.md) — why `formrdesc` and
    the relcache init dance matter for nailed catalogs.
  - [`syscache-catcache-internals`](../idioms/syscache-catcache-internals.md)
    — when adding a column that becomes a syscache key.
- Subsystems:
  - [`utils-cache`](../subsystems/utils-cache.md) — syscache / relcache
    machinery.
  - [`access-heap`](../subsystems/access-heap.md) — `heap_form_tuple` and
    deforming rules that constrain field ordering.
- Issues: none registered yet for this change-class; surface any
  half-broken `.dat` edits via `progress/scenarios-coverage.md`.
- Reference patch (canonical_commit):
  `git -C source show 99f8f3fbbc8` — "Add relallfrozen to pg_class".
