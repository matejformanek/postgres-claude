# `src/backend/utils/activity/pgstat_xact.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~360
- **Source:** `source/src/backend/utils/activity/pgstat_xact.c`

Transactional integration for the cumulative-stats system. Two main
duties: (1) per-subxact tuple-count stacking, (2) deferred
create/drop of variable-numbered stats entries.

## Subxact tuple stack

- `PgStat_SubXactStatus` is a per-subxact list of
  `PgStat_TableXactStatus` records (insert/update/delete deltas for
  every table touched at this nest level).
- `AtEOXact_PgStat_Relations(xact_state, isCommit)` and
  `AtEOSubXact_PgStat_Relations(xact_state, isCommit, nestDepth)` merge
  child into parent on commit, or discard on abort. After all per-rel
  stacks merge into top-level `PgStat_TableStatus.t_counts`, the next
  `pgstat_report_stat` flushes those into shmem.

## Pending drop/create

- `pgstat_create_*` (for new objects like a freshly-created table) and
  `pgstat_drop_*` are deferred until commit because the catalog row
  itself is transactional. `xact_state->pending_drops` is the dlist of
  PgStat_PendingDroppedStatsItem; on commit, we delete the shared
  hashtable entries via `pgstat_drop_entry_internal`. On abort, we just
  discard the list. Symmetric for "pending creates" (used to roll back
  ENTER_ENTRY references taken during the xact).

## Two-phase commit

Registered as RMID `TWOPHASE_RM_PGSTAT_ID`: `pgstat_twophase_postcommit`
and `pgstat_twophase_postabort` apply the captured tuple deltas to the
permanent stats after a `COMMIT PREPARED` / `ROLLBACK PREPARED`.
[from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
