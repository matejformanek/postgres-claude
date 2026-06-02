# `src/backend/replication/logical/slotsync.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 2099
- **Source:** `source/src/backend/replication/logical/slotsync.c`
- **Note:** Lives under `logical/` but its header is `replication/slotsync.h`.

## Purpose

Synchronizes failover-enabled logical slots from a primary to its
physical standbys, so promotion preserves logical-replication progress.
Two drivers: the slot-sync worker (auto if `sync_replication_slots=on`)
or the SQL function `pg_sync_replication_slots()`. PG 17+. [from-comment]
(`slotsync.c:11-26`)

## State semantics

Local mirror slots are `RS_TEMPORARY` until they are "sync-ready", then
flipped to `RS_PERSISTENT`. Sync-ready requires:

1. Standby has flushed WAL ≥ remote slot's `confirmed_flush_lsn`.
2. Standby's catalog xmin not behind remote slot's needs (no rows
   missing).
3. Standby can build a consistent snapshot at `restart_lsn` before
   reaching `confirmed_flush_lsn` (otherwise post-promotion decoding
   could lose changes — corrupt-snapshot scenario described at
   `:28-35`). [from-comment]

The skip reasons map 1:1 to `SlotSyncSkipReason` (`slot.h:80-90`).

## Coordination state

`SlotSyncCtxStruct` (`:112`): `pid` of syncing process,
`stopSignaled` (set by startup on promotion), `syncing` (mutex barring
concurrent syncs), `last_start_time` (restart throttle).

## Spine

- `ReplSlotSyncWorkerMain` — bgworker entry; loop:
  `ValidateSlotSyncParams` → connect via libpqwalreceiver →
  `SyncReplicationSlots` → wait → repeat.
- `SyncReplicationSlots` — fetch remote slot list via
  `pg_show_replication_slots()` over the connection, for each: maybe
  create local copy, call `update_local_synced_slot`, mark
  RS_TEMPORARY/RS_PERSISTENT.
- `wait_for_slot_activity` — adaptive sleep: shorter if any slot was
  updated last cycle.
- `drop_local_obsolete_slots` — drop locally-synced slots no longer
  present on the primary.
- `HandleSlotSyncMessageInterrupt` / `ProcessSlotSyncMessage` — signal
  handling (PROCSIG_SLOTSYNC_MESSAGE).
- `ShutDownSlotSync` — promotion-time tear-down by startup process.

## Coupling

- Sets `IsSyncingReplicationSlots()` true so `slot.c:ReplicationSlotCreate`
  accepts `failover=true` for RS_TEMPORARY slots (otherwise refused
  during recovery — see `slot.c:405-420`).
- Reuses snapbuild and reorderbuffer load/restore code paths
  indirectly via the slot it creates.

## Open questions

- Race on promotion: `stopSignaled` documented as not reset because we
  don't support demotion. If demotion ever lands this becomes a hazard.
  [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [architecture/replication.md](../../../../../architecture/replication.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
