# `src/include/utils/relmapper.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

The *catalog relmap*: maps `pg_class.oid` → `RelFileNumber` for
**nailed catalogs whose filenumber cannot be stored in their own
`pg_class` row** (chicken-and-egg). Stored on disk in
`global/pg_filenode.map` (shared) or `<dboid>/pg_filenode.map` (per
DB) [from-comment: line 3].

## Public API

### WAL record [verified-by-code: lines 25-35]

`XLOG_RELMAP_UPDATE` carries `xl_relmap_update {dbid, tsid, nbytes,
data[]}`. `dbid=0` ⇒ the shared (global) map.

### Lookup / update [lines 38-48]

- `RelationMapOidToFilenumber(relationId, shared)`
- `RelationMapFilenumberToOid(filenumber, shared)`
- `RelationMapOidToFilenumberForDatabase(dbpath, relationId)` —
  reads another database's map; used by pg_upgrade and pg_dumpall.
- `RelationMapCopy(dbid, tsid, srcdbpath, dstdbpath)` — used by
  CREATE DATABASE.
- `RelationMapUpdateMap(relationId, fileNumber, shared, immediate)`
- `RelationMapRemoveMapping(relationId)`

### Invalidation [lines 50-51]

`RelationMapInvalidate(shared)`, `RelationMapInvalidateAll()`.

### Lifecycle hooks [lines 53-57]

`AtCCI_RelationMap`, `AtEOXact_RelationMap(isCommit,
isParallelWorker)`, `AtPrepare_RelationMap`,
`CheckPointRelationMap`, `RelationMapFinishBootstrap`.

### Init [lines 61-63]

3-phase: `RelationMapInitialize`, `…Phase2`, `…Phase3` — mirrors
the bootstrap relcache init sequence.

### Parallel-worker serialization [lines 65-67]

`EstimateRelationMapSpace`, `SerializeRelationMap`,
`RestoreRelationMap`.

### Recovery [lines 69-71]

`relmap_redo`, `relmap_desc`, `relmap_identify`.

## Invariants

- **INV-NAILED-ONLY** [inferred] Only nailed catalogs appear in the
  relmap; other relations get their filenumber from
  `pg_class.relfilenode`.
- **INV-ATOMIC** [inferred from the WAL record] Map file updates are
  atomic via rename — the WAL record carries the full new contents,
  not a delta.
- **INV-PARALLEL** [verified-by-code: line 54] Parallel workers
  re-receive the relmap via `SerializeRelationMap` — they must NOT
  re-read the on-disk file because the leader's transaction may
  have updated it.

## Trust boundary (Phase D)

- **On-disk `pg_filenode.map` parsing**: tampering with this file
  (which sits in `global/` or `<dboid>/`) can misdirect catalog
  opens to the wrong physical file. Read protection is filesystem
  permissions on `$PGDATA`; in-process protection is a CRC in the
  file body (verified at load time in `relmapper.c`).
- **`RelationMapOidToFilenumberForDatabase`**: callable from
  pg_upgrade-style code paths; reads another database's map without
  acquiring the per-DB locks. Trust-on-disk-but-CRC-checked.
- **WAL replay** (`relmap_redo`): runs in startup process; a
  malformed `xl_relmap_update` could in principle assert; production
  paths come from `RelationMapUpdateMap` so size matches.
- **pg_upgrade catalog-trust angle** (A8/A12): relmap is part of
  the surface that pg_upgrade copies wholesale; corruption here
  could survive an upgrade.

## Cross-refs

- `common/relpath.h` — `RelFileNumber` type.
- `utils/inval.h` — relmap invalidation participates in relcache
  inval broadcast.
- `access/xlog.h` — WAL.
- A8/A12 — pg_upgrade catalog-trust angle.

## Issues

- [ISSUE-PHASE-D: `RelationMapOidToFilenumberForDatabase` reads
  another database's map without database-level locks; safety
  relies on caller having acquired pg_upgrade-style exclusivity
  (medium)] — line 41.
- [ISSUE-DOC: header doesn't document the on-disk CRC discipline;
  contributors might assume the file is plain text (low)] —
  no comment line covers it.
