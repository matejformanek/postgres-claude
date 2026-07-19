# src/backend/utils/cache/relmapper.c

## Purpose

Maintains the catalog-OID → relfilenumber mapping for the small set of "mapped"
catalogs whose pg_class.relfilenode is forced to zero — i.e. `pg_class` itself
and every other nailed-cache catalog (must be openable without consulting
pg_class), plus all shared catalogs (since a per-database pg_class can't
authoritatively store the file path of a global object). Two on-disk files:
`global/pg_filenode.map` for shared catalogs and `base/<dboid>/pg_filenode.map`
per database. [from-comment] (`relmapper.c:5-29`)

## Role in PG

- Pre-pg_class lookup gate: relcache calls `RelationMapOidToFilenumber`
  during bootstrap of a Relation when `pg_class` itself isn't accessible.
- Provides the only "commit" mechanism for VACUUM FULL / CLUSTER of a
  mapped catalog: the rewrite is committed by atomically renaming
  `pg_filenode.map.tmp` over `pg_filenode.map` (`relmapper.c:64-69`),
  *not* by a pg_class row update. Because of this, mapped catalogs
  can only be rewritten by operations with no other transactional
  effects (`relmapper.c:18-29`).

## Key functions

Public API:
- `RelationMapOidToFilenumber(relationId, shared)` — `relmapper.c:166`. Linear
  scan of `local_map`/`shared_map`; the file is tiny (≤ MAX_MAPPINGS=64
  entries, `relmapper.c:82`) so this is cheap.
- `RelationMapFilenumberToOid(filenumber, shared)` — `relmapper.c:219`. Reverse
  lookup; used by `relfilenumbermap.c` for shared catalogs.
- `RelationMapOidToFilenumberForDatabase(dbpath, relationId)` — `relmapper.c:266`.
  For tools that need to peek at another database's local map (e.g. dropdb
  cleanup).
- `RelationMapCopy(dbid, tsid, srcdbpath, dstdbpath)` — `relmapper.c:293`.
  CREATE DATABASE template-copy path.
- `RelationMapUpdateMap(relationId, fileNumber, shared, immediate)` —
  `relmapper.c:326`. The mutator. Stages the change in
  `pending_*_updates` (or `active_*_updates` if `immediate=true`),
  asserting `MAX_MAPPINGS` not exceeded.
- `RelationMapRemoveMapping(relationId)` — `relmapper.c:439`. Used on abort to
  undo a pending update.
- `AtCCI_RelationMap` / `AtEOXact_RelationMap` / `AtPrepare_RelationMap` /
  `CheckPointRelationMap` — txn / 2PC / checkpoint integration
  (`relmapper.c:505-624`).
- `RelationMapFinishBootstrap` / `RelationMapInitialize` — startup
  hooks (`relmapper.c:626-712`).
- Parallel-worker serialization: `EstimateRelationMapSpace`,
  `SerializeRelationMap`, `RestoreRelationMap` (`relmapper.c:714-764`).
- WAL replay: `relmap_redo(record)` (`relmapper.c:1097`) applies
  `XLOG_RELMAP_UPDATE` records.

Internal I/O:
- `load_relmap_file(shared, lock_held)` / `read_relmap_file(map, dbpath,
  lock_held, elevel)` — read the file under `RelationMappingLock`
  LW_SHARED; fail FATAL on any error including bad magic, out-of-range
  `num_mappings`, or CRC mismatch (`relmapper.c:766-865`). Windows
  rename-while-open quirk drives the open-after-lock / close-before-release
  ordering (`relmapper.c:805-811`).
- `write_relmap_file(newmap, write_wal, send_sinval, preserve_files,
  dbid, tsid, dbpath)` — `relmapper.c:890`. Asserts caller holds
  `RelationMappingLock` LW_EXCLUSIVE. Computes CRC, writes to
  `pg_filenode.map.tmp`, `durable_rename`s over `pg_filenode.map`,
  optionally emits a WAL record and an sinval.
- `perform_relmap_update(shared, updates)` — `relmapper.c:1040`. Glue
  that holds the lock, merges, writes, sends sinval.

## State / globals

- `shared_map`, `local_map` (`relmapper.c:113-114`) — currently-known disk
  contents.
- `active_shared_updates`, `active_local_updates`,
  `pending_shared_updates`, `pending_local_updates` — staging areas for
  the txn-vs-immediate distinction. `pending_*` is filled by
  `RelationMapUpdateMap(.., /*immediate=*/false)` then promoted at
  CommandCounterIncrement to `active_*`, finally flushed on commit.
- `RELMAPPER_FILEMAGIC = 0x592717` (`relmapper.c:74`) — versioned by
  changing this constant; an old file with the wrong magic is rejected
  outright.
- `MAX_MAPPINGS = 64` (`relmapper.c:82`) — hard cap on entries. Raise
  if PG ever needs more nailed/shared catalogs.

## Phase D notes

- The file is **critical**: corruption / loss is unrecoverable (no
  automatic repair), hence the CRC + atomic rename design. `read_relmap_file`
  hardcodes elevel ≥ ERROR and the public path uses FATAL — the backend
  dies if it can't read its own filenode map (`relmapper.c:768-771`).
- The bounded `RelMapFile` struct (≤ MAX_MAPPINGS entries) sits comfortably
  inside a single sector, which is why a torn write is unlikely; nevertheless
  the rename-into-place pattern is the actual durability guarantee, not the
  size.
- WAL integration is unusual: `XLOG_RELMAP_UPDATE` records the *entire* new
  map contents, not a delta (`relmap_redo` on `relmapper.c:1097` calls
  `write_relmap_file` with the whole record payload). [inferred from name]

## Potential issues

- [ISSUE-correctness: hardcoded `MAX_MAPPINGS=64`. If a future patch
  adds new nailed catalogs that pushes a real cluster over 64,
  `RelationMapUpdateMap` will `elog(ERROR, "attempt to write bogus
  relation mapping")` (`relmapper.c:910-911`) — but the more interesting
  failure is that an old binary reading a newer-format file with
  num_mappings > 64 will refuse to start (FATAL at
  `relmapper.c:849-854`). Backwards-compat tripwire (low)]
- [ISSUE-state-transition: comment at `relmapper.c:119-122` says
  "currently, map updates are not allowed within subtransactions" but
  this is not enforced by an Assert — a future caller could violate it
  silently (maybe)]
- [ISSUE-undocumented-invariant: lock-ordering for
  `RelationMappingLock` (LWLock) relative to relcache locks isn't
  documented in this file. The "load file after acquiring lock,
  close before releasing" Windows-driven ordering is here, but global
  lock-order discipline isn't (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils`](../../../../../issues/utils.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [idioms/parallel-state-propagation.md](../../../../../idioms/parallel-state-propagation.md)
- [idioms/relcache-build.md](../../../../../idioms/relcache-build.md)

- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)