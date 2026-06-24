# `src/backend/replication/logical/relation.c`

- **Last verified commit:** `9a60f295bcb1`
- **Lines:** 961
- **Source:** `source/src/backend/replication/logical/relation.c`

## Purpose

Maintains the apply-worker's per-session cache mapping remote
`LogicalRepRelation` (from the publisher's 'R' message) to a local
`Relation`, including an `AttrMap` for column-name reordering when the
schemas differ. Also tracks updatability, replica-identity index choice,
and tablesync state (`relstate`, `statelsn`). [from-comment]

## Key structure

`LogicalRepRelMapEntry` (`logicalrelation.h:19-40`):

- `remoterel` — copy of the publisher's relation description.
- `localrelvalid` — invalidation flag; revalidate on next
  `logicalrep_rel_open`.
- `localreloid`, `localrel`, `attrmap`, `updatable`, `localindexoid`.
- `state`, `statelsn` — tablesync state for this rel.

## Spine

- `logicalrep_relmap_update` — called from `apply_handle_relation` when
  publisher sends an 'R' message. Looks up local rel by name in
  publisher's schema (or `pg_catalog`), builds the attrmap, decides
  replica-identity index via `GetRelationIdentityOrPK`.
- `logicalrep_rel_open(remoteid, lockmode)` — open the local relation;
  revalidate on invalidation; lock + return entry.
- `logicalrep_rel_close` — close + unlock.
- `IsIndexUsableForReplicaIdentityFull` — eligibility check for using a
  btree index when RI is FULL.
- `logicalrep_partmap_*` — parallel cache for partition routing.

Invalidation hook: relcache invalidations set `localrelvalid = false`.

## Coupling

Used by `worker.c` (`apply_handle_*`), `tablesync.c` (during catchup),
and `conflict.c` (to identify arbiter indexes).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
