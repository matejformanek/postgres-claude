# execReplication.c

- **Source:** `source/src/backend/executor/execReplication.c` (1166 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Helpers used by the **logical replication apply worker** to find and modify
target rows. Bypasses the normal SQL executor: given the replicated old/new
tuple, locate the target row by replica identity index (or seqscan), then
apply the INSERT/UPDATE/DELETE. [from-comment] `:3-9`

## Lookup

- `build_replindex_scan_key(ScanKey skey, rel, idxrel, slot)` `:58` — fill
  a ScanKey array from the replica-identity columns of `slot`.
- `RelationFindReplTupleByIndex(rel, idxoid, lockmode, searchslot, outslot)`
  `:182` — index-driven lookup using the REPLICA IDENTITY index (PK by
  default, or USER INDEX, or NOTHING which is an error here). Locks the
  found tuple with the requested LockTupleMode and returns it in outslot.
  Handles `LockWaitBlock` semantics so the apply worker waits for
  conflicting transactions.
- `RelationFindReplTupleSeq(rel, lockmode, searchslot, outslot)` `:370` —
  fallback sequential scan for REPLICA IDENTITY FULL: every column of every
  row is compared. Uses the table AM's equality machinery (with type-specific
  comparison).

## Apply primitives

- `ExecSimpleRelationInsert(resultRelInfo, estate, slot)` `:810` — heap_insert
  + ExecInsertIndexTuples + AFTER ROW triggers; bypasses BEFORE row triggers
  (apply worker fires only AFTER).
- `ExecSimpleRelationUpdate(resultRelInfo, estate, epqstate, searchslot, slot)`
  `:906` — table_tuple_update + index update for modified indexes + AFTER
  triggers. If EvalPlanQual is needed (concurrent update), uses epqstate.
- `ExecSimpleRelationDelete(resultRelInfo, estate, epqstate, searchslot)`
  `:996` — table_tuple_delete + AFTER triggers.

## Other

- `CheckCmdReplicaIdentity(rel, cmd)` — checks at executor start that the
  target relation has a sufficient replica identity for the requested
  command (otherwise `cannot update/delete from … because it does not
  have a replica identity and publishes updates`).
- Conflict reporting via `replication/conflict.h` — surfaces
  insert_exists/update_missing/delete_missing details in the log when the
  replica row state diverges from the publisher's.

## Tags

- [verified-by-code] entry points + signatures.
- [from-comment] purpose statement.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
