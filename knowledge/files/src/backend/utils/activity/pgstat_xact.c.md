# `src/backend/utils/activity/pgstat_xact.c`

- **Last verified commit:** `d774576f6f0`
- **Lines:** ~387
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

- `pgstat_create_transactional` (for new objects like a freshly-created
  table) and `pgstat_drop_transactional` are deferred until commit
  because the catalog row itself is transactional. Both funnel through
  `create_drop_transactional_internal` (`pgstat_xact.c:335`), which
  pushes a `PgStat_PendingDroppedStatsItem` onto
  `xact_state->pending_drops` — a single **dclist** holding both
  creates and drops, discriminated by the item's `is_create` flag
  (there is no separate "pending creates" list). At end-of-xact,
  `AtEOXact_PgStat_DroppedStats` (`pgstat_xact.c:67`) walks the list:
  on commit it drops the entries for *dropped* objects, on abort it
  drops the entries for *created* objects, via
  `pgstat_drop_entry(kind, dboid, objid, /* nowait */ true)`
  (`pgstat_xact.c:88`,`:97`). Entries that cannot be freed immediately
  are counted in `not_freed_count` and a
  `pgstat_request_entry_refs_gc()` is issued (`:105`) rather than
  blocking. [verified-by-code]

## Two-phase commit

This file's 2PC surface is the *prepare* side plus drop-item
(de)serialization — NOT the tuple-delta post-commit hooks. At PREPARE,
`AtPrepare_PgStat` (`pgstat_xact.c:191`) and `PostPrepare_PgStat`
(`:211`) delegate to `AtPrepare_PgStat_Relations` /
`PostPrepare_PgStat_Relations` (in `pgstat_relation.c`); note
`AtEOXact_PgStat` is deliberately not called during PREPARE (`:208`).
`pgstat_get_transactional_drops` (`:272`) serializes the pending-drop
list into `xl_xact_stats_item[]` for the 2PC state file, and
`pgstat_execute_transactional_drops` (`:314`) replays them (also on
`is_redo`) after `COMMIT PREPARED` / `ROLLBACK PREPARED`, again via
`pgstat_drop_entry(..., /* nowait */ true)` with the same
`not_freed_count` + GC-request fallback.

The tuple-delta hooks `pgstat_twophase_postcommit` /
`pgstat_twophase_postabort` (registered under `TWOPHASE_RM_PGSTAT_ID`)
live in `pgstat_relation.c`, not here. [verified-by-code]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
