# src/include/replication/slotsync.h

## Purpose

Exports for the **slot synchronization** worker introduced in PG17: a
standby-side background worker that periodically pulls logical-replication
slot state from the primary via a libpq connection so that, after a
controlled failover, the new primary already has up-to-date logical slots
("failover slots"). Source pin
`4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

Before PG17 a logical replication subscription could not survive a
publisher failover because the subscription's slot lived only on the old
primary. PG17 added the concept of a **failover-eligible slot** (the
`failover` boolean in `ReplicationSlotPersistentData`) and a worker on
each physical standby that connects back to the primary (using the same
`primary_conninfo` / `primary_slot_name` that the walreceiver uses) and
mirrors the failover slots into the standby's own `pg_replslot/`
directory. After promotion the new primary already holds the slot at
roughly the correct `restart_lsn` / `confirmed_flush_lsn`, so subscribers
can reconnect with minimal data loss. The header is consumed by the
slot sync worker entry point, postmaster spawn code, and the
`pg_sync_replication_slots()` SQL function.

## Key types/struct fields

- `sync_replication_slots` (line 19) — GUC, bool, enables the background
  worker on the standby. [verified-by-code]
- `SlotSyncShutdownPending` (line 22) — `volatile sig_atomic_t` flag set
  by the SIGUSR2 / shutdown signal handler `HandleSlotSyncMessageInterrupt`.
  [from-comment]
- `PrimaryConnInfo`, `PrimarySlotName` (lines 28-29) — the same GUCs the
  walreceiver uses; the slot sync worker reuses them rather than having
  its own connection string. [verified-by-code]
- `CheckAndGetDbnameFromConninfo(void)` (line 31) — extracts the dbname
  the worker should connect to (logical slots are per-database). Returns
  a palloc'd C string. [verified-by-code]
- `ValidateSlotSyncParams(int elevel)` (line 32) — sanity check for the
  combined `wal_level >= logical` / valid `primary_conninfo` / non-empty
  `primary_slot_name` requirement. [from-comment]
- `ReplSlotSyncWorkerMain` (line 34) — `pg_noreturn` entry point for the
  bgworker spawned by the postmaster. [verified-by-code]
- `SyncReplicationSlots(WalReceiverConn *wrconn)` (line 39) — the actual
  per-cycle sync routine. Takes an already-open WalReceiverConn so it
  can be called from either the worker or the SQL function
  `pg_sync_replication_slots()`. [verified-by-code]
- `IsSyncingReplicationSlots(void)` (line 38) — query helper used by
  slot.c to refuse certain operations while sync is in progress.
  [verified-by-code]

## Phase D notes

This is a trust boundary inversion compared to the rest of replication:
normally the *standby* trusts the primary as the authoritative source
of WAL. Here the standby also trusts the primary's claims about slot
ownership, `restart_lsn`, `confirmed_flush`, `two_phase`, `plugin` name,
and `database`. A compromised primary that lies about a slot's
`confirmed_flush` could push the standby's local copy past a real
subscriber's checkpoint; after failover the subscriber would lose
changes silently. There is no cryptographic anchoring of slot state.

The standby uses `primary_conninfo` — the same credential as the
walreceiver — to read slot state. If the standby's `primary_conninfo`
points to a different host than the operator believes (e.g. via DNS
poisoning or a misconfigured `host=` entry), the standby will happily
mirror an attacker-supplied slot definition including an arbitrary
`plugin` name. The plugin name doesn't trigger `dlopen` on the standby
(decoding doesn't run there) but at promotion time the new primary will
dlopen exactly the name that was synced — see `output_plugin.h.md` for
the dlopen-anything concern.

`pg_sync_replication_slots()` is a SQL-callable wrapper, gated by
function ACL only — any role granted EXECUTE can trigger a sync cycle
against the primary, including a sync of slots they don't own. The
slot-name validation lives in `slot.c`'s usual path; there is no
additional ACL on which slots may be synced.

## Potential issues

- [ISSUE-trust-boundary: standby believes primary's claim about every
  failover slot's plugin name, confirmed_flush, two_phase, and
  database; a primary compromise propagates straight into the new
  primary post-failover (sev=likely)]
- [ISSUE-info-disclosure: `pg_sync_replication_slots()` SQL function
  exposes slot metadata for all failover slots to any role with EXECUTE
  (default `public`?), including slots owned by other subscriptions
  (sev=maybe)]
- [ISSUE-state-transition: `SlotSyncShutdownPending` is checked
  cooperatively in the worker loop; a worker stuck in a libpq read
  (network black-hole) cannot observe the flag without a libpq timeout
  GUC (sev=unlikely)]
- [ISSUE-undocumented-invariant: header doesn't say what happens to a
  half-synced slot if the worker exits mid-write to
  `pg_replslot/<name>/state` — relies on slot.c's atomic-rename
  discipline (sev=maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/replication.md](../../../../subsystems/replication.md)
