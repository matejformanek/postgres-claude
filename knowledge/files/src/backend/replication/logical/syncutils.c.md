# `src/backend/replication/logical/syncutils.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 281
- **Source:** `source/src/backend/replication/logical/syncutils.c`

## Purpose

Shared helpers between tablesync and sequencesync workers. Provides
`FinishSyncWorker` (graceful exit) and the subscription-relations
state-tracking machinery used to know when the apply worker needs to
re-scan `pg_subscription_rel`. [from-comment]

## SyncingRelationsState

Three-valued enum (`:37-42`): NEEDS_REBUILD, REBUILD_STARTED, VALID.
Used so a relcache or sub-rel invalidation only forces *one* rebuild even
under concurrent invalidations.

## FinishSyncWorker

Commits any open xact, flushes WAL, logs the per-type "has finished"
message (`am_sequencesync_worker()` vs `am_tablesync_worker()` branch),
resets `last_seqsync_start_time` for the launcher, exits. (`:49-...`)
