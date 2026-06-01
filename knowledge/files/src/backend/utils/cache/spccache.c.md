# spccache.c

- **Source path:** `source/src/backend/utils/cache/spccache.c`
- **Lines:** 238
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `spccache.h`, `commands/tablespace.c` (`tablespace_reloptions`), `access/reloptions.c`.

## Purpose

Cache for parsed `pg_tablespace.spcoptions`. Each entry holds a `TableSpaceOpts *` (random_page_cost, seq_page_cost, effective_io_concurrency, maintenance_io_concurrency) — used by the planner per-table-to-tablespace cost lookup. [from-comment, spccache.c:6-9]

## Top-of-file comment

> "We cache the parsed version of spcoptions for each tablespace to avoid needing to reparse on every lookup. Right now, there doesn't appear to be a measurable performance gain from doing this, but that might change in the future as we add more options." [spccache.c:6-9]

## Public surface

- `get_tablespace_page_costs(Oid, double *, double *)` (183).
- `get_tablespace_io_concurrency(Oid)` (216).
- `get_tablespace_maintenance_io_concurrency(Oid)` (230).
- Static: `get_tablespace` (108), `InvalidateTableSpaceCacheCallback` (55), `InitializeTableSpaceCache` (79).

## Key types / structs

- `TableSpaceCacheEntry` (38) — `{Oid oid; TableSpaceOpts *opts;}`.
- `TableSpaceOpts` defined in `commands/tablespace.h`.
- Global `TableSpaceCacheHash` (36), keyed by spc oid, initial size 16.

## Key invariants and locking

- **`InvalidOid` ⇒ default tablespace.** Since spcid comes from `pg_class.reltablespace`, InvalidOid means "use database default" (`MyDatabaseTableSpace`). [from-comment, spccache.c:114-117]
- **Coarse invalidation.** Any pg_tablespace inval blows away the entire cache. "Currently, we just flush them all. This is quick and easy and doesn't cost much, since there shouldn't be terribly many tablespaces, nor do we expect them to be frequently modified." [from-comment, spccache.c:50-53]
- **Pointer instability.** "Pointers returned by this function should not be stored, since a cache flush will invalidate them." [from-comment, spccache.c:104-105]
- **Not transactional.** "This value is not locked by the transaction, so this value may be changed while a SELECT that has used these values for planning is still executing." This is acceptable because the values are planner cost hints, not correctness-critical. [from-comment, spccache.c:178-180]
- **Build-then-insert ordering.** Same gotcha as attoptcache — fetch and parse the syscache row first, then insert into the hash, to survive cache flushes during parsing. [from-comment, spccache.c:161-164]
- **Default fallbacks.** If `opts` is NULL or a particular field is `< 0`, returns the GUC default (`random_page_cost`, `seq_page_cost`, `effective_io_concurrency`, `maintenance_io_concurrency`). [verified-by-code, spccache.c:192-237]

## Functions of note

- `get_tablespace_page_costs` — used by the planner cost estimator for every table being scanned.

## Cross-references

- **Called by**: cost-estimation paths in the planner (`costsize.c`), `bufmgr.c` for IO concurrency.
- **Calls into**: syscache (`TABLESPACEOID`), `tablespace_reloptions`.

## Open questions

None.

## Confidence tag tally

verified-by-code: 3 — from-comment: 5 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
