# indexcmds.c

- **Source path:** `source/src/backend/commands/indexcmds.c`
- **Lines:** 4659
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catalog/index.c` (`index_create`, `index_build`, `index_drop` — the low-level catalog munging), `access/heap/heapam.c` (validate-scan), the per-AM `*xlog.c` files for index WAL.

## Purpose

"POSTGRES define and remove index code." [from-comment, indexcmds.c:3-4] Implements `CREATE INDEX`, `CREATE INDEX CONCURRENTLY` (CIC), `REINDEX` and `REINDEX CONCURRENTLY` (the concurrent variants share most of their machinery via `ReindexRelationConcurrently`), `ALTER INDEX ... ATTACH PARTITION`, opclass/opfamily resolution helpers used elsewhere, and the `WaitForOlderSnapshots` helper used to make CIC visible.

## Public surface (line cites)

- `CheckIndexCompatible` (179) — pre-flight check used by ALTER TABLE to decide whether an existing index can be reused after a type change without rebuild.
- `WaitForOlderSnapshots` (436) — wait until every transaction whose snapshot predates a chosen point has finished. The synchronisation primitive that makes CIC and concurrent DETACH safe. Walks `GetCurrentVirtualXIDs` and calls `VirtualXactLock(vxid, true)`. [verified-by-code]
- `DefineIndex` (545) — **The main entry point**, ~1300 lines. Handles both plain CREATE INDEX and CIC.
- `ComputeIndexAttrs` (1881) — resolve column/expr list to attnums + opclasses + collations + options. Used by both DefineIndex and ALTER TABLE ADD CONSTRAINT.
- `ResolveOpClass` (2286), `GetDefaultOpClass` (2371), `GetOperatorFromCompareType` (2473) — opclass lookup helpers consumed widely (FK matching, statscmds, partition bound exclusion).
- `makeObjectName` (2546), `ChooseRelationName` (2634), `ChooseIndexName` (2702), `ChooseIndexNameAddition` (2757), `ChooseIndexColumnNames` (2791) — auto-naming used when the user does not supply a name. Truncates to `NAMEDATALEN-1` and appends a `_N` suffix if needed.
- `ExecReindex` (2852) — entry from utility dispatch. Switches on `kind` and routes to `ReindexIndex`, `ReindexTable`, `ReindexMultipleTables`, or `ReindexPartitions`.
- `ReindexRelationConcurrently` (3596) — the concurrent REINDEX state machine, ~800 lines.
- `IndexSetParentIndex` (4476), `update_relispartition` (4608) — ALTER INDEX ATTACH PARTITION plumbing.
- `set_indexsafe_procflags` (4646) — set `MyProc->statusFlags |= PROC_IN_SAFE_IC` so other backends compute snapshots that exclude us; used in CIC/REINDEX CONCURRENTLY phases.

## CREATE INDEX CONCURRENTLY — the three-transaction protocol [HIGH-RISK]

The CIC path inside `DefineIndex` runs as **three separate transactions** (verifiable by `CommitTransactionCommand` / `StartTransactionCommand` calls inside DefineIndex):

1. **Txn 1 — Insert catalog entry, marked NOT ready and NOT valid.** Acquires `ShareUpdateExclusiveLock` on the heap (so concurrent INSERT/UPDATE/DELETE continues but no schema changes). Calls `index_create` with `concurrent=true` (`INDEX_CREATE_CONCURRENT` flag). The index is now visible to writers, which will start maintaining it. Commits, then `WaitForOlderSnapshots` to ensure every backend has seen the new index entry before we start scanning.
2. **Txn 2 — Build the index from the current snapshot.** Calls `index_build`, which scans the heap with `SnapshotAny` filtering, writes the index pages, marks `indisready=true` (visible to readers as a maintenance index). Commits, then `WaitForOlderSnapshots` again.
3. **Txn 3 — Validate.** Final scan to pick up any tuples whose insertion was concurrent with txn 1/2 but whose xact had already committed; mark `indisvalid=true`. Commit.

If any phase fails, the index is left invalid (visible in `pg_index.indisvalid=false`); user must `REINDEX` or `DROP`. The `set_indexsafe_procflags` call is critical: it tells other backends "you may ignore my snapshot when computing horizons for VACUUM and freezing" — otherwise CIC would block VACUUM indefinitely on a large table. [verified-by-code, indexcmds.c:545-1850, 4646]

## REINDEX CONCURRENTLY (`ReindexRelationConcurrently`)

Similar 3-transaction shape but more complex because the existing index must be swapped out:

1. Create a new "transient" index alongside the old one (same definition, `pg_class` name suffix `_ccnew`).
2. Build, validate, mark new index ready/valid (exact same wait-for-snapshots pattern as CIC).
3. Swap relfilenodes between old and new indexes (`index_concurrently_swap`), then drop the now-transient old index.

Partitioned indexes recurse: each leaf partition's index is reindexed independently; `ReindexPartitions` (3376) walks the partition tree.

## Opclass resolution

`ResolveOpClass` and `GetDefaultOpClass` are the canonical lookups; `GetOperatorFromCompareType` (2473) is the modern (PG 18+) way to find an opclass's `=`, `<`, etc. operators by `CompareType` (replaces the older "strategy number" lookup at the API surface, though strategy numbers still drive the catalog). Used by FK matching, partition-bound exclusion, hash partition equality, and the new MERGE statement.

## Tests

- `src/test/regress/sql/create_index.sql`, `index_including.sql`, `index_including_gist.sql`.
- `src/test/regress/sql/reindex_catalog.sql`, `reindex_partition.sql`.
- `src/test/isolation/specs/reindex-*.spec`, `create-index-concurrently-*.spec` — these are the regression net for the wait-for-snapshots logic.

## Open questions

- Whether the `PROC_IN_SAFE_IC` exception is also honoured by serializable-snapshot SSI (predicate locking) is not traced here. [unverified]
- The handling of expression indexes whose expression references a function that becomes invalid mid-CIC — fail-fast path was not deep-read. [unverified]

## Confidence tag tally

`[verified-by-code]=6 [from-comment]=1 [unverified]=2`
