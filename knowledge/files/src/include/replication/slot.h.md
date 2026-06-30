# src/include/replication/slot.h

## Purpose

Declares the central PostgreSQL **replication slot** machinery: the
`ReplicationSlot` shared-memory struct, the on-disk `ReplicationSlotPersistentData`
sub-struct, persistency modes (`RS_PERSISTENT` / `RS_EPHEMERAL` /
`RS_TEMPORARY`), invalidation causes, slot-sync skip reasons, and the C API
for creating, acquiring, releasing, dropping, and persisting slots. Backs both
physical (streaming) and logical replication. Source pin
`4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

Replication slots are the durable handle a downstream consumer (walreceiver,
logical decoder, subscription apply worker, `pg_receivewal`) holds against the
upstream to demand WAL/xmin retention. They are the only PG mechanism that
gives a non-superuser the ability to make the server **retain WAL forever** and
hold back the xmin horizon (for logical slots, also `catalog_xmin`). Almost
every replication failure mode — pg_wal disk-full, vacuum bloat on the
publisher, failover-slot drift, conflict-detection slot stalls — traces back
to a misbehaving or abandoned slot. The header is included by
`backend/replication/slot.c`, walsender, the slot sync worker, `pg_upgrade`,
and the `pg_replication_slots` SRF.

## Key types/struct fields

- `PG_REPLSLOT_DIR "pg_replslot"` (line 21) — on-disk directory under
  `$PGDATA` where each slot's `state` file lives. [verified-by-code]
- `CONFLICT_DETECTION_SLOT "pg_conflict_detection"` (line 28) — a reserved
  slot name retaining dead tuples for logical-rep conflict detection.
  Reserved-name check is in `ReplicationSlotValidateName`. [from-comment]
- `enum ReplicationSlotPersistency` (lines 43-48) — `RS_PERSISTENT` survives
  restarts; `RS_EPHEMERAL` is a transient pre-persist state used during
  creation; `RS_TEMPORARY` is dropped on session end / error.
  [verified-by-code]
- `enum ReplicationSlotInvalidationCause` (lines 58-69) — bitmask values
  `RS_INVAL_WAL_REMOVED` (1), `RS_INVAL_HORIZON` (2), `RS_INVAL_WAL_LEVEL`
  (4), `RS_INVAL_IDLE_TIMEOUT` (8). Comment at line 54 explicitly warns
  future authors that new causes MUST be powers of two AND must bump
  `RS_INVAL_MAX_CAUSES` (line 72, currently 4). [from-comment]
- `enum SlotSyncSkipReason` (lines 80-90) — five reasons the slot-sync
  worker may skip syncing a remote slot to a standby (PG17+). Persisted
  only in shared memory, not on disk (see comment lines 277-282).
  [verified-by-code]
- `ReplicationSlotPersistentData` (lines 95-162) — on-disk image: `name`,
  `database` (Oid; `InvalidOid` for physical slots), `persistency`, `xmin`,
  `catalog_xmin`, `restart_lsn`, `invalidated` (cause bit), `confirmed_flush`,
  `two_phase_at`, `two_phase`, `plugin` (NameData — the C string passed
  unchanged to `load_external_function`), `synced`, `failover`.
  [verified-by-code]
- `ReplicationSlot` (lines 180-285) — shmem image. Mutex `mutex` (slock_t)
  protects per-slot fields; `ReplicationSlotControlLock` (LWLock) protects
  `in_use` and the slot array. Hot fields: `active_proc` (ProcNumber of
  current owner or `INVALID_PROC_NUMBER`), `effective_xmin` /
  `effective_catalog_xmin` (latest values that have been written to disk —
  for logical slots they MAY differ from `data.xmin`/`data.catalog_xmin`
  which represent the in-memory truth), `dirty` / `just_dirtied`,
  `inactive_since`, `last_saved_restart_lsn`, `last_saved_confirmed_flush`,
  `slotsync_skip_reason`. [verified-by-code]
- `SlotIsPhysical(slot)` / `SlotIsLogical(slot)` (lines 287-288) — the
  discriminator is `data.database != InvalidOid`. A physical slot has no
  database scope; a logical slot is permanently bound to one database.
  [verified-by-code]
- `ReplicationSlotSetInactiveSince` (lines 305-317) — static-inline guard
  that skips setting `inactive_since` if the slot is already invalidated,
  so the displayed timestamp reflects the *last live* inactivity not the
  invalidation moment. [verified-by-code]
- GUCs (lines 326-329): `max_replication_slots`,
  `max_repack_replication_slots`, `synchronized_standby_slots`,
  `idle_replication_slot_timeout_secs`. [verified-by-code]
- API surface (lines 332-385): create / persist / drop / alter / acquire /
  release / save / mark-dirty / cleanup; the synthesis helpers
  `ReplicationSlotsComputeRequiredXmin`,
  `ReplicationSlotsComputeRequiredLSN`,
  `ReplicationSlotsComputeLogicalRestartLSN`; the per-DB enumerator
  `ReplicationSlotsCountDBSlots`; the failover-slot
  `WaitForStandbyConfirmation`. [verified-by-code]
- `CheckSlotPermissions()` (declared line 378) — backend impl at
  `slot.c:1688` requires `has_rolreplication(GetUserId())`, i.e. the
  `REPLICATION` role attribute. Same gate for physical and logical slot
  creation. [verified-by-code]

## Phase D notes

The slot is the most powerful trust-boundary primitive in the entire
backend short of superuser: holding one lets a non-superuser pin xmin,
pin WAL on disk, and (via the `plugin` field) trigger `dlopen` of an
arbitrary shared library at decoding start. The whole API hinges on
exactly one permission check, `has_rolreplication`, and there is no
quota — a role with REPLICATION can create up to `max_replication_slots`
slots and each one independently retains WAL until dropped or
invalidated.

`max_slot_wal_keep_size_mb` default is `-1` (unbounded) — confirmed at
`source/src/backend/access/transam/xlog.c:142` and
`postgresql.conf.sample:362` ("`#max_slot_wal_keep_size = -1    # in
megabytes; -1 disables`"). With the default, **a single abandoned
persistent slot will eventually fill the WAL volume and shut the cluster
down**; this is by-design for replication safety but is the textbook
DoS-by-default knob.

The `invalidated` cause is stored as a single enum value on disk
(`ReplicationSlotPersistentData.invalidated`), but the enum values are
already a power-of-two bitmask in anticipation of multi-cause
invalidation; `InvalidateObsoleteReplicationSlots` accepts a `uint32
possible_causes` mask (line 364). The on-disk field is a single cause;
the function takes a mask. This is an in-flight design with a
forward-compatible mask in the API but a scalar on disk.

`slotsync_skip_reason` lives only in shmem (comment lines 277-282
explains why: "temporary slots are dropped after server restart, persisting
slotsync_skip_reason provides no practical benefit"). A standby that
crashes while skipping sync for a temporary slot loses the diagnostic
reason — observability hole on diagnosing why a failover slot never
became synced.

The `last_saved_restart_lsn` comment (lines 247-270) explicitly admits
restart_lsn can move **backward** during physical streaming startup
because the walreceiver may re-receive segments and report them as
flushed. This is an invariant violation of "monotonic restart_lsn" that
external monitoring tooling routinely assumes. Worth a dedicated note in
the replication subsystem doc.

## Potential issues

- [ISSUE-trust-boundary: REPLICATION role attribute is the single gate
  for slot creation; same role can create physical AND logical slots and
  for logical slots can pick ANY .so plugin name (sev=likely)]
- [ISSUE-dos: `max_slot_wal_keep_size = -1` by default → one abandoned
  persistent slot fills pg_wal and PANICs the cluster; documented
  trade-off, no quota per-slot or per-role (sev=likely)]
- [ISSUE-dos: no per-role quota on slot count; a single REPLICATION role
  can consume all `max_replication_slots` shmem entries (sev=maybe)]
- [ISSUE-state-transition: `RS_EPHEMERAL` is a transient state during
  slot creation — if the creating backend crashes between
  `ReplicationSlotCreate` and `ReplicationSlotPersist`, the slot is
  dropped on next startup (verified by header comment lines 38-41), but
  the on-disk `state` file may still exist in `pg_replslot/` and is
  cleaned by `StartupReplicationSlots`; concurrent shmem readers seeing
  EPHEMERAL must not treat it as PERSISTENT (sev=unlikely)]
- [ISSUE-undocumented-invariant: `restart_lsn` is NOT monotonic — it can
  move backward during physical-streaming startup (comment lines 247-270).
  External monitors assuming monotonicity will mis-alert (sev=maybe)]
- [ISSUE-info-disclosure: a logical slot pins `catalog_xmin` cluster-wide
  even though it is bound to one database — VACUUM on OTHER databases'
  shared catalogs is held back by ANY logical slot, leaking the existence
  and approximate xmin of slots in other DBs through pg_class bloat
  observable to any user (sev=maybe)]
- [ISSUE-state-transition: `invalidated` on disk is a single
  ReplicationSlotInvalidationCause value but the API
  `InvalidateObsoleteReplicationSlots(uint32 possible_causes, ...)`
  takes a bitmask; if two causes fire simultaneously (e.g. WAL_REMOVED +
  IDLE_TIMEOUT) only one is recorded (sev=maybe)]
- [ISSUE-undocumented-invariant: `slotsync_skip_reason` not persisted —
  diagnostic data lost across restart, hampering postmortem of a
  failover-slot promotion that never happened (sev=unlikely)]

## Synthesized by
<!-- backlinks:auto -->
- [architecture/replication.md](../../../../architecture/replication.md)
- [idioms/replication-slot-advance.md](../../../../idioms/replication-slot-advance.md)

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->

