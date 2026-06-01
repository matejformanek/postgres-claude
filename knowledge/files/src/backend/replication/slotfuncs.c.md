# `src/backend/replication/slotfuncs.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 963
- **Source:** `source/src/backend/replication/slotfuncs.c`

## Purpose

SQL-callable wrappers around `slot.c`. Implements
`pg_create_physical_replication_slot`,
`pg_create_logical_replication_slot`, `pg_drop_replication_slot`,
`pg_get_replication_slots` (the catalog view), `pg_replication_slot_advance`,
`pg_logical_replication_slot_advance`, `pg_copy_physical_replication_slot`,
`pg_copy_logical_replication_slot`, `pg_sync_replication_slots`. Also
exposes the slot-sync skip-reason enum mapping (`SlotSyncSkipReasonNames`,
`:31-37`). [from-comment]

## Notable helpers

- `create_physical_replication_slot` (`:48`) — Assert no `MyReplicationSlot`,
  `ReplicationSlotCreate` then optional `ReplicationSlotReserveWal` if
  `immediately_reserve`.
- `create_logical_replication_slot` — sets up a LogicalDecodingContext to
  find the start LSN.
- `pg_get_replication_slots` (SRF) — projects slot fields including
  `slotsync_skip_reason` (new in PG 18).

## Coupling

- All real work happens in `slot.c`. This file is a thin permissions /
  argument-parsing layer.
- `pg_sync_replication_slots()` delegates to `slotsync.c`.
