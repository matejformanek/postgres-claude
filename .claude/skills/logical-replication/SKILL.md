---
name: logical-replication
description: PostgreSQL's logical replication — publisher-side WAL decoding + subscriber-side apply — plus everything under `src/backend/replication/logical/`. Loads when the user asks about logical decoding, `pg_logical_slot_get_changes`, publications / subscriptions, output plugins (pgoutput / test_decoding), reorder buffer, historic snapshots (SnapBuild), the apply worker + parallel apply, conflict resolution (PG 18+ conflict tracking), replication origins, replication slots (physical vs logical, `slot.c` + `slotsync.c`), streaming mode for in-progress transactions, tablesync's initial COPY, or debugging apply-worker crashes / slot advancement / catalog_xmin retention. Skip when the ask is about physical streaming replication (walsender/walreceiver, `replication/basebackup*.c`, `replication/walsender.c` in isolation) — those are the sibling `replication` subsystem, mostly disjoint code paths.
when_to_load: Add/debug logical-decoding output plugin; add a new logical replication protocol message (has scenario `add-new-replication-message`); investigate apply-worker / parallel-apply behavior; touch reorder buffer / SnapBuild / slotsync internals; extend conflict resolution (PG 18+ new area); understand why a logical slot won't advance or a replication origin doesn't track expected LSN.
companion_skills:
  - locking
  - error-handling
  - process-lifecycle
---

# logical-replication — logical decoding + apply

Logical replication has **two sides** you must not confuse:

- **Publisher side** — reads WAL, decodes it into logical changes, hands them to an *output plugin* (usually `pgoutput`) which serializes them as protocol messages sent over a walsender.
- **Subscriber side** — the *apply worker* receives those messages, applies INSERT/UPDATE/DELETE to the local database, and tracks its progress via a *replication origin*.

Both live under `src/backend/replication/logical/` (20 files). Neither is a simple codebase — `worker.c` alone is 194 KB; `reorderbuffer.c` is 162 KB.

## The file map

### Publisher (decoding) side

| File | KB | Role |
|---|---:|---|
| `decode.c` | 40 | WAL-record-to-logical-change decoder. Reads XLogRecords, dispatches to reorderbuffer callbacks. |
| `reorderbuffer.c` | 162 | The **big one**. Assembles decoded changes into transaction-shaped batches, spills to disk on memory pressure, handles subtransactions, TOAST reassembly, streaming (in-progress) transactions. |
| `snapbuild.c` | 65 | Historic-snapshot construction — SnapBuild state machine (BUILDING → FULL_SNAPSHOT → CONSISTENT) that lets decoding see committed catalog state as of a chosen LSN. |
| `logical.c` | 69 | Logical-decoding context (`LogicalDecodingContext`), CreateInitDecodingContext (for slot creation), CreateDecodingContext (for reading). |
| `logicalctl.c` | 21 | Utilities for the logical-decoding control interface. |
| `logicalfuncs.c` | 10 | SQL-callable helpers: `pg_logical_slot_get_changes`, `pg_replication_slot_advance` etc. |
| `message.c` | 3 | `pg_logical_emit_message` — arbitrary in-WAL logical messages. |

### Slot management

| File | KB | Role |
|---|---:|---|
| `slotsync.c` | 63 | Slot-sync worker — replicates logical-slot state from primary to standby (PG 17+ failover-safe slots). |
| `sequencesync.c` | 22 | Sequence-value sync (PG 18+ sequences-in-logical-replication). |

### Subscriber (apply) side

| File | KB | Role |
|---|---:|---|
| `worker.c` | **194** | **THE apply worker**. Main loop, message dispatch, INSERT/UPDATE/DELETE handlers, error handling, snapshot management. When users say "apply worker" this is the file. |
| `applyparallelworker.c` | 50 | Parallel apply worker (PG 16+ streaming mode with parallelism). Coordinator process partitions incoming stream across N leaf workers. |
| `launcher.c` | 46 | Logical-rep launcher aux process. Starts + monitors apply workers per subscription. |
| `tablesync.c` | 50 | Initial-sync worker. Per-table: COPY the base data, then hand off streaming to the main apply worker at the right LSN. |
| `relation.c` | 27 | Subscriber-side relation cache. Maps publisher-side OIDs to subscriber-side relations via names, tracks column mapping. |
| `origin.c` | 47 | Replication origins — track subscriber progress + prevent circular replication. `pg_replication_origin_*` SQL functions live here. |
| `conflict.c` | 20 | Conflict detection + logging (PG 18+ conflict tracking). |
| `proto.c` | 31 | Logical replication protocol — encode/decode `pgoutput` messages. Shared between publisher (walsender via pgoutput) and subscriber (worker.c). |
| `syncutils.c` | 8 | Small helpers shared between apply and tablesync. |

### Output-plugin default

`src/backend/replication/pgoutput/pgoutput.c` — the pgoutput plugin (default logical output). Implements the callbacks that `logical.c` invokes. Custom output plugins (like Debezium's decoderbufs, test_decoding) are contrib modules or extensions.

## The decode → apply flow

```
[primary] insert row on table T
   ↓
WAL record written
   ↓
walsender starts a logical replication connection
   ↓
CreateDecodingContext + slot state
   ↓
decode.c reads XLogRecords sequentially
   ↓
reorderbuffer accumulates txn's changes; may spill to disk
   ↓
on COMMIT: reorderbuffer replays changes in-order, in the historic
snapshot from snapbuild
   ↓
output plugin (pgoutput) callback: apply_change → serialize as
'I'/'U'/'D' protocol messages
   ↓
walsender sends messages over the wire
   ↓
[subscriber apply worker (worker.c)] reads messages, dispatches
   ↓
apply_dispatch → apply_handle_insert / apply_handle_update / _delete
   ↓
subscriber-side execute the change (with conflict handling in
PG 18+)
   ↓
LogicalRepApplyLoop tracks progress via replorigin_session_setup
```

## Slots — physical vs logical

Both physical and logical replication use **replication slots** (`src/backend/replication/slot.c` — sibling, not in the logical/ subdir). Difference:

- **Physical slot** — reserves WAL for a physical standby / walsender. No catalog_xmin. Just a `restart_lsn`.
- **Logical slot** — reserves WAL AND catalog snapshots (via `catalog_xmin`) for logical decoding. Requires more machinery — snapbuild state, output plugin, spill-file directory in `pg_replslot/<name>/`.

Slot mismanagement is a common failure mode: a stale logical slot pins WAL indefinitely and blocks vacuum from removing dead catalog tuples. Monitor `pg_replication_slots.confirmed_flush_lsn` vs `pg_current_wal_lsn`.

## Streaming vs non-streaming apply

Non-streaming: the publisher accumulates a whole transaction in the reorderbuffer, sends everything on COMMIT. Simple, but slow for large transactions (memory pressure, spill).

Streaming (PG 14+): publisher sends transaction changes as they decode (with a `Stream Start / Stream Stop` bracket), subscriber accumulates into a spool file until the streamed transaction commits, then applies.

Parallel apply (PG 16+): with streaming + `streaming = parallel` on the subscription, the subscriber's launcher spawns leaf workers (`applyparallelworker.c`) that apply streamed transactions concurrently. Requires no schema-conflicting sub-transactions.

## Conflict tracking (PG 18+)

`conflict.c` implements the four conflict types the apply worker can detect:

1. **`insert_exists`** — subscriber has a row with the same PK as the incoming INSERT.
2. **`update_missing`** — incoming UPDATE targets a row the subscriber doesn't have.
3. **`update_differ`** — target row exists but doesn't match the OLD tuple's values.
4. **`delete_missing`** — same shape for DELETE.

Each logs a row into `pg_stat_subscription_conflicts` (via pgstat) and can trigger the subscription's `disable_on_error` policy.

## Common patch shapes

### Add a new logical replication protocol message

Scenario exists: `knowledge/scenarios/add-new-replication-message.md`. Short:
- New byte-code in `proto.c` for the message shape.
- Encoder call from `pgoutput.c` (publisher).
- Decoder + dispatch in `worker.c` (subscriber).
- Version-gate via `LOGICAL_PROTO_VERSION_*` in `proto.h`.

### Extend output-plugin callbacks

- New callback in `include/replication/output_plugin.h` (e.g. `stream_change_cb`).
- Wire it in `logical.c`'s `LogicalDecodingContext.*` and the reorderbuffer replay path.
- Update `pgoutput.c` + `test_decoding` (in contrib) to implement it.
- Extension output plugins may need updates or fall back gracefully via NULL-callback checks.

### Add a new conflict type

- Extend `ConflictType` enum in `include/replication/conflict.h`.
- Detection + logging in `conflict.c` (`ReportApplyConflict`).
- Update `pg_stat_subscription_conflicts` schema + counter in `pgstat_subscription.c` (touches pgstat-framework).

### Debug slot-not-advancing

- Check `pg_replication_slots.confirmed_flush_lsn` — subscriber isn't acknowledging.
- Check subscriber's `pg_stat_subscription.last_msg_receipt_time` — is the apply worker running?
- Check `pg_stat_subscription.received_lsn` vs `pg_current_wal_lsn` on publisher — is receipt lagging?
- Check `pg_replication_slots.wal_status` — if `lost`, WAL was recycled.

## Pitfalls

- **`catalog_xmin` retention is the silent killer** — a logical slot that stops advancing prevents vacuum from removing dead catalog tuples. Cluster performance degrades silently over days.
- **Reorderbuffer spill files** — `pg_replslot/<name>/xid-*` files. If a slot stalls, spill can fill the disk. Not always obvious it's the slot's fault.
- **`snapbuild` needs a clean starting point** — creating a logical slot on a busy system may take a while (has to see all in-progress txns commit or abort before reaching CONSISTENT).
- **Origin sessions leak on error** — if apply worker crashes mid-transaction, `replorigin_session_setup` state may need manual reset via `pg_replication_origin_advance`.
- **Parallel apply requires no PROVIDED savepoints** — a transaction using SAVEPOINT can't be parallelized; the leaf worker will error and the coordinator will retry serially.
- **`decoding_context.streaming = false` is default** — a slot may not receive streamed messages unless the subscriber says `streaming = on`. Common misconfig.
- **Publisher-side vs subscriber-side `_PG_init`** — for output plugin extensions: publisher loads it via `output_plugin_options`; subscriber-side extensions load differently. Don't share state.
- **`pgoutput` vs `test_decoding` vs custom** — pgoutput speaks the wire format the subscriber expects; test_decoding is a debugging text serializer, NOT wire-compatible.
- **Slot-sync races on failover** — `slotsync.c` is a background worker on standby that replicates slot state. If the standby is promoted mid-sync, slots may lag or be inconsistent. Use `pg_sync_replication_slots()` explicitly before failover.

## Related corpus

- **Idioms** (9 covered): `apply-conflict-resolution`, `apply-handlers-insert-update-delete`, `apply-streaming-and-parallel`, `apply-worker-loop`, `apply-worker-loop-and-dispatch`, `logical-decoding-snapshot`, `output-plugin-callbacks`, `replication-origin-tracking`, `replication-slot-advance`.
- **Subsystem**: `replication` (the parent doc — covers physical + logical high-level).
- **Scenario**: `add-new-replication-message`.
- **Related idiom**: `tablesync-initial-copy` (COPY-based bootstrap for a new subscription).
- **Related session logs**: `2026-06-02-replication-synthesis.md`, `2026-06-04-a8-include-replication.md`.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --scenario add-new-replication-message
python3 scripts/corpus-chain.py --file src/backend/replication/logical/worker.c
python3 scripts/corpus-chain.py --idiom apply-worker-loop
```

These surface the tight neighborhood: the 20 files under `logical/`, the 9 apply/decoding idioms, and the pgoutput integration point.

## Boundary

**Use this skill** for the `src/backend/replication/logical/` tree + `pgoutput` + apply-worker + reorderbuffer + slot management.

**Don't use** for:
- **Physical streaming replication** — walsender/walreceiver/basebackup are the parent `replication` subsystem; different code paths, though they share slot infrastructure.
- **`walsender` / `walreceiver`** — those handle both physical and logical connections; use the parent `replication` subsystem doc.
- **Foreign data wrappers** (`postgres_fdw`) — that's not replication.
- **BDR / pglogical / Debezium** — external / contrib output plugins; they build ON logical decoding but their internals are their own.
