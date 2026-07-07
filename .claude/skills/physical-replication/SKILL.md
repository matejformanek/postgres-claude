---
name: physical-replication
description: PostgreSQL's physical streaming replication — walsender (primary side, `replication/walsender.c`) + walreceiver (standby side, `replication/walreceiver.c`) + slots (`replication/slot.c`) + synchronous replication (`syncrep.c`). Covers the streaming protocol variant, hot standby, standby feedback, synchronous commit, WAL sender/receiver state machines, and the physical-slot semantics that differ from logical slots. Loads when the user asks about streaming replication, hot standby, `pg_basebackup`, synchronous_commit levels, walsender/walreceiver state, primary_conninfo, physical replication slots, standby feedback (`hot_standby_feedback`), or `pg_wal_replay_*` recovery-progress functions. Skip when the ask is about logical replication (`replication/logical/`) — sibling but very different code path.
when_to_load: Configure or debug streaming replication; understand walsender/walreceiver state machine; touch synchronous commit / feedback; investigate slot management (physical); work with base-backup infrastructure.
companion_skills:
  - logical-replication
  - process-lifecycle
  - error-handling
---

# physical-replication — streaming to a physical standby

Physical (aka streaming, aka binary) replication ships raw WAL bytes from primary to standby. The standby applies them via the same recovery machinery used at startup — replaying block-level changes. Sibling to logical replication but MUCH simpler code path: no decoding, no output plugin, no per-row conflict handling.

## The file map

| File | KB | Role |
|---|---:|---|
| `replication/walsender.c` | 134 | **Primary side.** The walsender is a backend spawned per replication connection. Reads WAL, sends it over the connection, handles feedback + syncrep signaling + timeline history. |
| `replication/walreceiver.c` | 47 | **Standby side.** The walreceiver is a distinct aux process on the standby. Establishes libpq connection to primary's walsender, receives WAL, writes to local pg_wal, signals startup process to replay. |
| `replication/walreceiverfuncs.c` | 11 | SQL-callable helpers on the standby side. |
| `replication/slot.c` | 97 | Replication slot infrastructure — physical AND logical share this file for the base mechanics (create/drop/persistence). |
| `replication/slotfuncs.c` | 28 | SQL-callable slot functions. |
| `replication/syncrep.c` | 35 | Synchronous replication — primary waits for confirmed standby write / flush / apply based on `synchronous_commit`. |
| `access/transam/xlogrecovery.c` | — | The startup process's WAL replay engine. Called on the standby to consume WAL from walreceiver. |
| `backup/basebackup*.c` | — | pg_basebackup server-side implementation — makes a physical copy for a new standby. |

## The two processes

**Walsender** on the primary:
- Spawned per replication connection.
- Runs a state machine: `WALSNDSTATE_STARTUP` → `_BACKUP` → `_CATCHUP` → `_STREAMING` → `_STOPPING`.
- In STREAMING state, sends chunks of WAL as `XLogData` messages plus periodic `KeepAlive`.
- Receives `HotStandbyFeedback` from standby and updates `pg_stat_replication` view.
- If synchronous, participates in the `syncrep.c` signaling.

**Walreceiver** on the standby:
- One instance total (not per-slot).
- Connects to primary via libpq, negotiates the streaming protocol.
- Writes received WAL to local `pg_wal/` files.
- Reports progress back via feedback + `pg_stat_wal_receiver`.
- Cooperates with the startup process which does the actual replay.

## Physical vs logical slots

Physical slot:
- Reserves WAL for the standby's use — primary won't recycle WAL under `restart_lsn`.
- No catalog_xmin (no need — physical replay doesn't need catalog snapshots).
- Simpler: just a `restart_lsn` for the primary to track.
- Created by `pg_create_physical_replication_slot('name')`.

Logical slot (contrast):
- Reserves WAL AND catalog snapshots.
- Has an output plugin.
- SLRU (`pg_replslot/<name>/`) spill space.

## Streaming protocol

Walsender sends messages tagged with:

- `'w'` — WAL data chunk (with LSN + timestamp).
- `'k'` — KeepAlive (empty; probes liveness).

Walreceiver replies with:

- `'r'` — receipt confirmation (LSNs: written, flushed, applied).
- `'h'` — HotStandbyFeedback (xmin + catalog_xmin, if `hot_standby_feedback = on`).

Message boundaries + framing are the shared `replication/pgoutput` and libpq protocol layers.

## Synchronous replication semantics

`synchronous_commit` on the primary controls what happens before COMMIT returns to the client:

| Setting | Wait for |
|---|---|
| `off` | Nothing (fastest, unsafe on crash). |
| `local` | Local WAL flushed to disk. |
| `remote_write` | Primary's WAL flushed AND standby has written to memory (not necessarily to disk). |
| `on` (default) | Primary AND standby WAL flushed to disk. |
| `remote_apply` | Primary + standby flushed + standby applied. |

Which standby? Configured via `synchronous_standby_names` — either a name list or a quorum specification (PG 10+: `ANY 2 (a, b, c)`).

## Hot standby

When `hot_standby = on`, the standby accepts read-only queries during recovery. Complications:

- Snapshot conflicts — a long standby query may prevent the primary from removing tuples the query needs. Solutions:
  - `max_standby_streaming_delay` — cancel long queries if they block replay.
  - `hot_standby_feedback` — send xmin back to primary; primary keeps those tuples alive at the cost of freezing pressure.
- Locking conflicts — same story for locks needed by replay.

## Common patch shapes

### Add a new replication feedback field

- Extend `HotStandbyFeedback` message structure in `libpq/pqcomm.h` etc.
- Sender updates (walreceiver) — extend the send.
- Receiver updates (walsender) — parse and store new field.
- View update — `pg_stat_replication` gets a new column.
- Docs.

### Change walsender state machine

Careful — the state transitions are checked in many places. Consider:
- The transition itself.
- Every check of the state.
- Failure paths that must reset state cleanly.

### Extend synchronous_standby_names semantics

Existing supports named priority and quorum. Extensions might add per-region grouping, latency-based selection, etc. Would touch `syncrep.c` `SyncRepGetSyncStandbysQuorum` + related.

### Debug "standby is falling behind"

- `pg_stat_replication` on primary — see write_lag, flush_lag, replay_lag.
- `pg_stat_wal_receiver` on standby — connection state, last_msg_receipt_time.
- `pg_wal_replay_pause_lsn()` / `pg_last_wal_replay_lsn()` — how far the standby has applied.
- Check for long queries on standby (via `pg_stat_activity`) blocking replay under high concurrency.

## Pitfalls

- **`synchronous_commit = off` is per-transaction** — you can set it locally in a session. Async transactions still write WAL, just don't wait.
- **`synchronous_standby_names` with unreachable standby BLOCKS commits** — a misconfigured name = your primary waits forever. Set `synchronous_commit = local` under emergency to unblock.
- **`hot_standby_feedback = on` retains xmin** — long standby queries + feedback + high write rate → wraparound risk on primary. Monitor.
- **Physical slot never expires** — a dropped standby's slot pins WAL forever. `pg_drop_replication_slot` is manual.
- **Walreceiver reset on error** — a transient network error may cause walreceiver to reconnect from scratch, replaying overlap. Usually fine; occasionally shows up as a spike in replay activity.
- **`max_standby_streaming_delay = -1`** means "wait forever for the query to finish". A standby with this set + a stuck query = replay stalls.
- **`hot_standby = off` allows recovery to catch up faster** — no snapshot conflicts. Sometimes recommended for CPU-heavy replay windows.
- **`primary_conninfo` password can leak into logs** — use `~/.pgpass` or a service definition instead.
- **Base backup via pg_basebackup includes UNLOGGED tables' init fork but not their main fork** — standby will re-init unlogged tables on promotion. Common surprise for test setups.
- **`archive_command` can conflict with slot-based replication** — both retain WAL; consider which method is authoritative.

## Related corpus

- **Subsystem**: `replication` (the parent doc — covers both physical + logical high-level).
- **Sibling skill**: `logical-replication` (very different code paths despite shared filenames).
- **Idioms**: `walsender-state-machine`, `wal-page-write-flush`, `wal-buffer-state`, `crash-recovery-startup`, `replication-origin-tracking` (logical-specific but adjacent).
- **Sessions**: `2026-06-02-replication-synthesis.md` — comprehensive replication doc write.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/replication/walsender.c
python3 scripts/corpus-chain.py --file src/backend/replication/walreceiver.c
python3 scripts/corpus-chain.py --idiom walsender-state-machine
```

## Boundary

**Use this skill** for streaming replication + walsender/walreceiver + physical slots + syncrep + hot standby.

**Don't use** for:
- **Logical replication** — `src/backend/replication/logical/` — completely separate code paths. See `logical-replication` skill.
- **WAL insertion / write / flush** on the primary — those are `access/transam/xlog.c` machinery; use `wal-buffer-state` idiom or `wal-and-xlog` skill.
- **Recovery / crash restart** — `access/transam/xlogrecovery.c` — used at startup regardless of replication.
- **Backup tools** — `pg_basebackup` invocation lives in `src/bin/pg_basebackup/`.
- **`pg_receivewal`** — external walreceiver; different implementation than backend walreceiver.
