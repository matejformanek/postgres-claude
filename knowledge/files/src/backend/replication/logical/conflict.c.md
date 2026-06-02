# `src/backend/replication/logical/conflict.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 651
- **Source:** `source/src/backend/replication/logical/conflict.c`

## Purpose

Conflict detection and reporting on the subscriber. Introduced in PG 18
to give DBAs visibility into what last-write-wins replication is masking.
Defines 8 conflict types (`ConflictType`, `conflict.h:31-62`):
`insert_exists`, `update_origin_differs`, `update_exists`, `update_missing`,
`delete_origin_differs`, `update_deleted`, `delete_missing`,
`multiple_unique_conflicts`. [from-comment]

## Spine

- `GetTupleTransactionInfo` (`:64`) — pull xmin + commit timestamp +
  origin from a local tuple (requires `track_commit_timestamp`).
- `ReportApplyConflict` (`:105`) — main reporter. Builds an `errdetail`
  combining info about all conflicting local rows (a single INSERT can
  hit multiple unique indexes), formats key column values, uses ereport
  at the elevel chosen by the caller (LOG normally, ERROR for
  `multiple_unique_conflicts` etc.).
- `errcode_apply_conflict` / `errdetail_apply_conflict` — per-type errcode
  + detail formatter.
- `build_index_value_desc` — pretty-print the conflicting index key.
- `InitConflictIndexes` — set up `ri_arbiter_indexes` from the local rel
  so apply DML can use `ExecCheckIndexConstraints`.

## Stats

The `conflict_count` array in `PgStat_StatSubEntry` is indexed by
`ConflictType` — comment warns to update stats code if you reorder the
enum. (`conflict.h:25-30`)

## Coupling

- Called by `apply_handle_{insert,update,delete}` paths in `worker.c`.
- Origin/timestamp info from the local row needs
  `track_commit_timestamp=on` to be meaningful.
- For `update_deleted`, the "retain dead tuples" mechanism in
  `worker.c`/`launcher.c` keeps the relevant dead heaps around.

## Synthesized by
<!-- backlinks:auto -->
- [architecture/replication.md](../../../../../architecture/replication.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
