# `src/backend/replication/slot.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 3291
- **Source:** `source/src/backend/replication/slot.c`

## Purpose

Replication-slot management — physical and logical. A slot is a
crash-safe, persistent piece of cluster state that prevents premature
removal of WAL or of dead tuples that some consumer still needs. Must
work on standbys (so cannot live in catalogs). Stored per-slot in
`$PGDATA/pg_replslot/<name>/state`, mirrored in shared memory.
[from-comment] (`slot.c:14-32`)

## On-disk format

`ReplicationSlotOnDisk` (`:67-86`) — magic + crc + version + length +
`ReplicationSlotPersistentData`. Constants: `SLOT_MAGIC = 0x1051CA1`,
`SLOT_VERSION = 5` (`:143-144`). Three derived size macros for checksum
boundaries (`:131-141`).

## Locking model

- `ReplicationSlotAllocationLock` (LWLock, exclusive) — allocate/free a
  slot.
- `ReplicationSlotControlLock` — shared to iterate, exclusive to flip
  `in_use`.
- Per-slot `mutex` (spinlock) — protects the slot's mutable fields.
- Per-slot `active_cv` (condition variable) — wait for the slot to be
  released by its current owner.
  [from-comment] (`slot.c:29-32`) [verified-by-code]

## Invalidation causes

`ReplicationSlotInvalidationCause` (defined in `slot.h:58-69`) is a
**bitmask** so a single invalidation pass can consider multiple causes:
RS_INVAL_WAL_REMOVED, RS_INVAL_HORIZON, RS_INVAL_WAL_LEVEL,
RS_INVAL_IDLE_TIMEOUT. Lookup table at `:115-121`.

## Spine functions

- `ReplicationSlotCreate` (`:378`) — full path: validate name, check
  failover/standby rules, take Allocation+Control locks, scan for name
  collision and free slot in the persistent or REPACK slice, init
  persistent + in-memory data, `CreateSlotOnDisk`, flip `in_use` and
  `active_proc = MyProcNumber`, create pgstat entry if logical, broadcast
  `active_cv`. (`:378-540`) [verified-by-code]
- `ReplicationSlotAcquire` (`:629`) — find slot, refuse if it's the
  internal `pg_conflict_detection` reserved slot (`:659-663`), use
  `active_cv` to wait for current owner unless `nowait`. Optional
  invalidation check.
- `ReplicationSlotRelease` (`:769`) — release ownership, save dirty,
  broadcast.
- `ReplicationSlotsComputeRequiredXmin` (`:1220`) — aggregate xmin over
  all in-use slots — feeds vacuum horizon.
- `ReplicationSlotsComputeRequiredLSN` (`:1302`) — aggregate restart_lsn
  for WAL retention.
- `ReplicationSlotsComputeLogicalRestartLSN` (`:1372`) — logical-only
  variant.
- `ReplicationSlotReserveWal` (`:1705`) — pin current WAL position as
  restart_lsn at slot creation.
- `InvalidatePossiblyObsoleteSlot` (`:1974`) — the **load-bearing**
  invalidator. If the slot is unacquired, mark `data.invalidated`, persist
  immediately. If acquired, signal owner with SIGTERM (or
  RECOVERY_CONFLICT_LOGICALSLOT if we're the startup process) and wait on
  `active_cv`, retry. Race-aware: rechecks the cause after re-acquiring
  the lock, because xmin/restart_lsn can advance under us. (`:1974-2187`)
- `InvalidateObsoleteReplicationSlots` (`:2214`) — checkpoint-driven
  wrapper that iterates all slots and applies the cause mask. Skips
  logical slots during binary upgrade. If it invalidates the last logical
  slot, requests disabling logical decoding. (`:2208-2228`)
- `CheckPointReplicationSlots` (`:2318`) — fsync each dirty slot file.
- `StartupReplicationSlots` (`:2396`) — load slots from disk at startup.
- `SaveSlotToPath`/`RestoreSlotFromDisk` (`:2518`, `:2681`) — on-disk
  serialization.

## Synchronized-standby-slots support

`SyncStandbySlotsConfigData` (`:95-104`) — flat GUC structure for
`synchronized_standby_slots`. `StandbySlotsHaveCaughtup` (`:3107`) and
`WaitForStandbyConfirmation` (`:3255`) gate logical decoding so a
logical-failover slot can't get ahead of physical standbys that must
inherit it.

## Persistency states

`RS_PERSISTENT` (crash-safe), `RS_EPHEMERAL` (in-progress create — dropped
on release/crash), `RS_TEMPORARY` (session-bound). (`slot.h:43-48`)

## Invariants

- Slots that are `synced` (mirrored from primary onto standby) are
  considered inactive for idle-timeout purposes because they don't decode
  locally. (`:1860-1872`) [verified-by-code]
- A walsender for an invalidated slot is signalled and the invalidated
  state is fsync'd **before** the slot is released. (`:2156-2180`)
- `restart_lsn` is cleared on RS_INVAL_WAL_REMOVED (`:2065-2069`).

## Open questions

- Comment at `:2061-2064` flags an XXX about preserving `restart_lsn`
  alongside `invalidated`. [from-comment]
- Reserved-slot list isn't exhaustive in this file: the only reserved
  name today is `pg_conflict_detection`. (`slot.h:28`)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
