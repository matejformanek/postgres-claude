# index.c

- **Source path:** `source/src/backend/catalog/index.c`
- **Lines:** ~4 600
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catalog/index.h`, `catalog/heap.c`, `commands/indexcmds.c` (CREATE INDEX parse/plan), each AM's `xxbuild.c`.

## Purpose

"code to create and destroy POSTGRES index relations". Interface routines (top comment, index.c:14-19): `index_create()`, `index_drop()`, `BuildIndexInfo()`, `FormIndexDatum()`. Plus a large block of REINDEX CONCURRENTLY plumbing (`index_concurrently_build/swap/set_dead`) and the validate_index machinery used by CREATE INDEX CONCURRENTLY. [from-comment]

## Public surface

- `index_create` (730) — **the catalog backend for CREATE INDEX.** Inserts the index pg_class row (relkind = INDEX or PARTITIONED_INDEX), pg_attribute rows, pg_index row (`UpdateIndexRelation`), recording opclass/collation/options. Records dependencies on table columns, opclasses, collations, and (for partitioned indexes) on the parent partitioned index. Calls `index_build` unless `INDEX_CREATE_SKIP_BUILD`. Inherits relpersistence and shared/mapped status from the heap. Refuses concurrent build on system catalogs and refuses concurrent exclusion constraints. [verified-by-code, index.c:730-1305]
- `index_create_copy` (1306) — clone an existing index definition (used for REINDEX CONCURRENTLY's transient index).
- `index_concurrently_build` (1503) — build phase of REINDEX CONCURRENTLY.
- `index_concurrently_swap` (1570) — the **catalog swap** at the end of REINDEX CONCURRENTLY: rewrites pg_index, pg_class, pg_constraint to point at the new index OID, leaving the old index marked dead and ready for `index_drop` in a later xact. The dance is described in detail in this function's comment.
- `index_concurrently_set_dead` (1841) — mark old index indisvalid=false, indisready=false, ready for cleanup.
- `index_constraint_create` (1903) — create the pg_constraint row that pairs with a UNIQUE/PRIMARY KEY/EXCLUDE index.
- `index_drop` (2140) — DROP INDEX (cataloged side). Two variants depending on `concurrent` flag; concurrent path multi-step with waits for snapshots.
- `BuildIndexInfo` (2446), `BuildDummyIndexInfo` (2506), `BuildSpeculativeIndexInfo` (2687), `FormIndexDatum` (2748) — runtime helpers used by the AM during insert/build: pack a heap tuple into the index's key vector.
- `index_update_stats` (2827) — write `relpages`, `reltuples`, `relallvisible`, `relhasindex` to pg_class via the inplace-update path. Used by both CREATE INDEX and VACUUM.
- `index_build` (3021) — **the bridge to the AM:** calls `indexRelation->rd_indam->ambuild(heap, index, indexInfo)`. Handles parallel-build worker request (only btree/GIN/BRIN today, gated by `amcanbuildparallel`), unlogged-index init-fork writeout, and progress reporting. Wraps the build in a SECURITY_RESTRICTED_OPERATION and a `RestrictSearchPath()` so user-defined functions in expression/predicate clauses can't perform mischief as the table owner. [verified-by-code, index.c:3021-3215]
- `IndexCheckExclusion` (3216) — post-build verification for EXCLUSION constraints.
- `validate_index` (3371), `validate_index_callback` (3504) — the CREATE INDEX CONCURRENTLY second-pass that inserts tuples missed by the first pass.
- `index_set_state_flags` (3524) — toggle `indisvalid`/`indisready`/`indislive` atomically via inplace update.
- `IndexGetRelation` (3604) — reverse lookup: index OID → heap OID.
- `reindex_index`, `reindex_relation` (further down) — the body of plain REINDEX.

## Locking contract

- Build phase (index.c:3070-3074) switches userid to relation owner and sets `SECURITY_RESTRICTED_OPERATION` + restricts search_path. This protects against a malicious table owner planting expression indexes that exploit the DB-owner running CREATE INDEX. [verified-by-code]
- Concurrent index build on system catalogs is rejected (index.c:856-860) "because we tend to release locks before committing in catalogs". [from-comment]
- Shared indexes cannot be created post-initdb (index.c:875-878) — no way to propagate the entry to other databases' pg_class. [verified-by-code]

## Confidence tag tally

`[verified-by-code]=6 [from-comment]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
