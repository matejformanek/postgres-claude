# Replication slot advance — restart_lsn + catalog_xmin progression

A replication slot is a persistent marker recording the
**oldest WAL position** and **oldest transaction XID** that a
downstream consumer (standby for physical, subscriber for
logical) still needs. The primary uses these markers to:

1. **Prevent WAL removal** before the consumer has streamed
   past the position (`restart_lsn`).
2. **Prevent VACUUM** from removing catalog tuples the
   consumer still might need (`catalog_xmin` — logical slots
   only).

The slot ADVANCES as the consumer confirms progress. Failure
to advance — inactive slot, network split, unconsumed
output — pins WAL + xmin indefinitely. The canonical bloat
hazard for replication-enabled clusters.

Anchors:
- `source/src/include/replication/slot.h:120-138, 332-358` —
  API + slot data fields [verified-by-code]
- `source/src/backend/replication/slot.c` — implementation
- `knowledge/subsystems/replication.md` — surrounding system
- `knowledge/idioms/xmin-horizon-management.md` — slot xmin
  contributes to the horizon

## The 3 key LSNs

[verified-by-code `slot.h:120-138, 210-271`]

| Field | Meaning |
|---|---|
| `restart_lsn` | Oldest WAL position the consumer needs |
| `confirmed_flush` | Logical-only: oldest position consumer has confirmed durable |
| `last_saved_confirmed_flush` | Disk-persisted confirmed_flush |
| `candidate_restart_lsn` | Proposed new restart_lsn, awaiting confirmation |
| `last_saved_restart_lsn` | Disk-persisted restart_lsn |

The split between in-memory and "last saved" is because slot
state is checkpoint-persistent. The in-memory value can advance
without immediate disk write; the saved value is the recovery
boundary.

## The 2 key XIDs

| Field | Meaning |
|---|---|
| `catalog_xmin` | Logical: oldest catalog snapshot consumer needs |
| `effective_catalog_xmin` | The xmin actually pinning the horizon |
| `candidate_catalog_xmin` | Proposed new catalog_xmin |

`catalog_xmin` is **logical-slot-only**. Physical slots don't
track it. A logical slot's `catalog_xmin` pins the catalog
horizon — VACUUM on `pg_class` etc. respects it so that
historical catalog reads during decoding still work.

## The advance protocol

1. Consumer streams a chunk of WAL.
2. Periodically (every few seconds), consumer sends a feedback
   message: "I've confirmed durable up to LSN X."
3. Slot's `confirmed_flush` advances to X.
4. Slot's `restart_lsn` advances to a WAL position from which
   decoding can resume (start-of-some-recent-running-xacts
   record).
5. `restart_lsn` advance permits checkpoint to remove old WAL
   segments below it.

The split between `confirmed_flush` and `restart_lsn` matters
for logical decoding: `restart_lsn` may be older than
`confirmed_flush` because decoding restart needs to read state
that predates the confirmed position.

## The walsender / consumer loop

For physical replication:
- `restart_lsn` = standby's reported `flush_lsn` (or its
  `apply_lsn` for hot-standby-feedback).
- No `catalog_xmin`.

For logical replication:
- `restart_lsn` = position of oldest in-progress decoding
  transaction.
- `catalog_xmin` = oldest catalog tuple needed for decoding
  in-progress transactions.
- `confirmed_flush` = subscriber's confirmed apply position.

## ReplicationSlotsComputeRequiredXmin

[verified-by-code `slot.h:358`]

```c
extern void ReplicationSlotsComputeRequiredXmin(bool already_locked);
```

Walks all active slots, finds the minimum `effective_xmin` and
`effective_catalog_xmin`, broadcasts to ProcArray. The
broadcast result is what
`GetOldestNonRemovableTransactionId` consults.

Called whenever a slot's xmin advances OR a slot is dropped —
the global horizon may move forward.

## The dirty + save semantics

[verified-by-code `slot.h:248-271`]

> Latest restart_lsn that has been flushed to disk. For
> persistent slots the flushed LSN should be taken into account
> when calculating the oldest LSN for WAL segments removal.
>
> Do not assume that restart_lsn will always move forward...

Subtlety: the in-memory `data.restart_lsn` can MOVE BACKWARD
in some cases (physical slot reading from a checkpoint that
predates the previous report). The persisted
`last_saved_restart_lsn` is the conservative truth — never
remove WAL below it.

`ReplicationSlotMarkDirty()` flags the slot for save at the
next checkpoint. Slots not marked dirty don't get re-persisted
even if their in-memory state changed.

## Slot vs WAL retention

WAL segments below `min(restart_lsn over slots) - wal_keep_size`
are eligible for removal at checkpoint. A single stuck slot
holds back ALL slots' WAL.

Diagnostic: a cluster's `pg_wal/` directory growing without
bound — check `pg_replication_slots.restart_lsn`. If one slot
is way behind, that's the blocker.

`max_slot_wal_keep_size` (PG 13+) caps the per-slot retention
— a slot whose `restart_lsn` falls more than `max_slot_wal_keep_size`
behind the current LSN is **invalidated** by the checkpointer.
Trades availability for bounded disk use.

## Slot invalidation

A slot can become `invalidated`:

- `wal_removed` — restart_lsn fell below `max_slot_wal_keep_size`.
- `rows_removed` — catalog_xmin fell below VACUUM horizon
  (logical only, rare).

An invalidated slot can no longer be used for streaming;
consumer must drop + recreate. Forfeiture of catch-up
capability.

## Production-use guidance

- **Monitor `pg_replication_slots`** for slots with
  `active = false` and old `restart_lsn`. Inactive slots are
  the canonical bloat cause.
- **Set `max_slot_wal_keep_size`** to bound disk use. Default
  unlimited (0) is dangerous in production.
- **Drop unused slots immediately.** A test slot left over
  from a one-off `pg_recvlogical` can pin WAL for the cluster
  lifetime.
- **Use `pg_replication_slot_advance(name, target_lsn)`**
  to force-advance a stuck slot if the consumer is offline
  and recovery isn't needed.
- **Logical slots are durable across restarts** by design.
  Drop them with `pg_drop_replication_slot` rather than
  letting them accumulate.

## Invariants

- **[INV-1]** `restart_lsn` is the OLDEST WAL the consumer
  needs; WAL retention sized to this.
- **[INV-2]** `catalog_xmin` is logical-slot-only; pins
  catalog horizon.
- **[INV-3]** `ReplicationSlotsComputeRequiredXmin` broadcasts
  the slot xmin minimum to ProcArray.
- **[INV-4]** `restart_lsn` may move backward in memory; the
  saved value is the conservative boundary.
- **[INV-5]** Invalidation = slot unusable; consumer must
  recreate.

## Useful greps

- All slot state fields:
  `grep -n 'restart_lsn\|catalog_xmin\|confirmed_flush' source/src/include/replication/slot.h`
- The horizon-broadcasting function:
  `grep -n 'ReplicationSlotsComputeRequiredXmin\|ReplicationSlotsComputeRequiredLSN' source/src/backend/replication/slot.c`
- Invalidation logic:
  `grep -RIn 'InvalidateObsoleteReplicationSlots\|wal_removed\|rows_removed' source/src/backend/replication`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/slot.c`](../files/src/backend/replication/slot.c.md) | — | implementation |
| [`src/include/replication/slot.h`](../files/src/include/replication/slot.h.md) | 120 | 332-358 — API + slot data fields |
| [`src/include/replication/slot.h`](../files/src/include/replication/slot.h.md) | — | slot struct + API |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/subsystems/replication.md` — the surrounding
  replication subsystem.
- `knowledge/idioms/xmin-horizon-management.md` — slot xmin
  is one horizon contributor.
- `knowledge/idioms/checkpoint-coordination.md` — checkpoint
  is the WAL-cleanup decision point.
- `knowledge/idioms/wal-record-construction.md` — the WAL
  that slots track positions in.
- `.claude/skills/wal-and-xlog/SKILL.md` — companion skill
  covering WAL + replication coordination.
- `source/src/include/replication/slot.h` — the slot
  struct + API.
- `source/src/backend/replication/slot.c` — implementation.
