---
name: replication-overview
description: Operational orientation for PostgreSQL replication — physical streaming vs archive vs logical decoding vs logical replication (PUB/SUB) vs synchronous commit. Names the GUC knobs (wal_level, max_wal_senders, max_replication_slots, max_logical_replication_workers, primary_conninfo, synchronous_standby_names) and points at the source files behind each flavor. Use whenever the user mentions replication, walsender, walreceiver, replication slot, logical decoding, output plugin, publication/subscription, conflict detection, sync replication, failover slots, or `pg_basebackup`. Conceptual reference: `knowledge/architecture/replication.md`.
---

# Replication — operational orientation

For the conceptual model (slot lifetimes, decoding pipeline, conflict semantics)
read `knowledge/architecture/replication.md`.

## Which kind of replication?

| If the user wants… | Flavor | Key GUCs |
|---|---|---|
| Hot standby, byte-identical copy, optional read queries | **Physical streaming** | `wal_level=replica`, `max_wal_senders`, `primary_conninfo`, `primary_slot_name` |
| Point-in-time recovery from a base backup + WAL archive | **Physical archive (PITR)** | `wal_level=replica`, `archive_mode`, `archive_command`/`archive_library`, `restore_command` |
| Stream row-level changes to a non-PG consumer (CDC, audit, custom sink) | **Logical decoding** via SQL or replication-protocol API + an output plugin | `wal_level=logical`, `max_replication_slots`, plugin (e.g. `test_decoding`, `pgoutput`) |
| Selective table replication between PG clusters, schema-agnostic upgrade, cross-version | **Logical replication** (`CREATE PUBLICATION` / `CREATE SUBSCRIPTION`) | `wal_level=logical`, `max_replication_slots`, `max_logical_replication_workers`, `max_sync_workers_per_subscription`, `max_parallel_apply_workers_per_subscription` |
| Wait-for-ACK durability on commit | **Synchronous replication** (overlay on physical or logical) | `synchronous_standby_names`, `synchronous_commit` |
| Standbys keep logical slots in sync for failover | **Slot sync** | `sync_replication_slots`, `synchronized_standby_slots`, slot `failover=true` |

[from-comment `source/src/backend/replication/walsender.c:5-18`;
from-comment `source/src/backend/replication/walreceiver.c:5-17`;
from-comment `source/src/backend/replication/syncrep.c:5-58`;
from-comment `source/src/backend/replication/logical/launcher.c:10-15,53-56`]

## wal_level — what it gates

- `minimal` — only crash recovery; no walsenders, no archive, no replication of
  any kind.
- `replica` — adds enough info for physical streaming and PITR archive.
- `logical` — additionally logs the data needed by `reorderbuffer` to reconstruct
  row changes (replica identity, etc.). Required for logical decoding and
  logical replication.

[from-code `source/src/backend/utils/misc/guc_tables.c:525,649` — `wal_level_options`, `effective_wal_level`]

## Where to look in source

### Physical streaming
- Sender: `source/src/backend/replication/walsender.c` (~134 KB). Handles
  replication-protocol commands `IDENTIFY_SYSTEM`, `BASE_BACKUP`,
  `CREATE_REPLICATION_SLOT`, `START_REPLICATION`. Grammar:
  `source/src/backend/replication/repl_gram.y:62-300`.
- Receiver: `source/src/backend/replication/walreceiver.c` + the dynamically
  loaded `libpqwalreceiver/` (keeps libpq out of the main server binary).
  [from-README `source/src/backend/replication/README:3-16`]
- Postmaster signaling for walsender lifecycle:
  `source/src/backend/replication/README:39-70`.

### Replication slots (physical and logical)
- `source/src/backend/replication/slot.c` — allocation, on-disk format,
  invalidation causes (`RS_INVAL_WAL_REMOVED`, `RS_INVAL_HORIZON`,
  `RS_INVAL_WAL_LEVEL`, `RS_INVAL_IDLE_TIMEOUT`).
  [from-code `source/src/include/replication/slot.h:58-72`]
- SQL surface: `slotfuncs.c`.
- Persistency states `RS_PERSISTENT | RS_EPHEMERAL | RS_TEMPORARY` —
  `source/src/include/replication/slot.h:43-48`.
- On-disk fields the user actually monitors: `restart_lsn`, `catalog_xmin`,
  `confirmed_flush`, `invalidated`, `two_phase`, `failover`, `synced`
  (`slot.h:95-162`).

### Logical decoding pipeline
- Coordinator: `source/src/backend/replication/logical/logical.c` — sets up
  `LogicalDecodingContext`, wraps output-plugin callbacks
  (`source/src/backend/replication/logical/logical.c:57-80`).
- Decoder: `source/src/backend/replication/logical/decode.c` — turns xlog
  records into `reorderbuffer` calls.
- Reassembly + spill-to-disk: `source/src/backend/replication/logical/reorderbuffer.c`
  (≈162 KB; ships in-progress transactions to disk under memory pressure —
  `reorderbuffer.c:33-83`).
- Catalog snapshots for decoding: `logical/snapbuild.c`.
- Output plugins: contract in `source/src/include/replication/output_plugin.h:36,216-243`
  (`_PG_output_plugin_init`, `OutputPluginCallbacks`). Built-in plugin used by
  logical replication: `source/src/backend/replication/pgoutput/`.

### Logical replication (PUB/SUB)
- Launcher (bgworker spawning per-subscription): `logical/launcher.c`.
- Apply worker: `logical/worker.c` (~194 KB). Streaming and two-phase notes at
  `worker.c:22-80`.
- Initial table sync: `logical/tablesync.c` — state machine
  `INIT → DATASYNC → FINISHEDCOPY → SYNCWAIT → CATCHUP → SYNCDONE → READY`
  (`tablesync.c:29-55`).
- Parallel apply: `logical/applyparallelworker.c`.
- Conflict logging (v18): `logical/conflict.c` — types in
  `ConflictTypeNames[]` (`conflict.c:27-36`).
- Sequence sync: `logical/sequencesync.c`.
- Slot sync to standby: `logical/slotsync.c`.
- Replication origins: `logical/origin.c`.

### Synchronous replication
- `source/src/backend/replication/syncrep.c` — wait queue on the primary; FIRST
  (priority) vs ANY (quorum) parsed by `syncrep_gram.y`
  (`syncrep.c:32-58`).

## Knob cheatsheet

```
# Primary (any flavor)
wal_level = replica | logical
max_wal_senders = 10
max_replication_slots = 10

# Standby (physical)
primary_conninfo = 'host=... user=replication'
primary_slot_name = 'standby_1'        # ties to a physical slot
hot_standby = on

# Logical replication subscriber
max_logical_replication_workers = 4    # launcher.c:54
max_sync_workers_per_subscription = 2  # launcher.c:55
max_parallel_apply_workers_per_subscription = 2  # launcher.c:56

# Synchronous
synchronous_standby_names = 'FIRST 2 (s1, s2, s3)'   # or 'ANY 2 (...)'
synchronous_commit = on | remote_apply | remote_write | local | off

# Failover slots (v17+)
sync_replication_slots = on            # on standby
synchronized_standby_slots = 's1,s2'   # on primary
```

## Common diagnostic views

- `pg_stat_replication` — one row per active walsender (on primary).
- `pg_stat_wal_receiver` — on standby.
- `pg_replication_slots` — slot state, `restart_lsn`, `confirmed_flush_lsn`,
  `wal_status`, `invalidation_reason`.
- `pg_stat_subscription`, `pg_stat_subscription_stats` — subscriber side.
- `pg_replication_origin_status` — apply progress per origin.

## Replication-protocol commands (psql `replication=true`)

`IDENTIFY_SYSTEM`, `CREATE_REPLICATION_SLOT slot {PHYSICAL|LOGICAL plugin} ...`,
`START_REPLICATION [SLOT s] {PHYSICAL %X/%X [TIMELINE n] | SLOT s LOGICAL %X/%X options}`,
`BASE_BACKUP (...)`, `READ_REPLICATION_SLOT`, `DROP_REPLICATION_SLOT`,
`TIMELINE_HISTORY`.
[from-code `source/src/backend/replication/repl_gram.y:62-300`]

## When to send the user deeper

- "Why is my slot blocking WAL recycling?" → slot's `restart_lsn` /
  `catalog_xmin`; see `knowledge/architecture/replication.md` §slots.
- "How do I write an output plugin?" → `output_plugin.h` callbacks +
  `contrib/test_decoding` as canonical example. Docs:
  https://www.postgresql.org/docs/current/logicaldecoding.html.
- "Subscriber missed an UPDATE" → conflict types in `logical/conflict.c`; in
  v18 logging is automatic.
- "Failover broke my logical subscription" → slot sync chapter + `failover`
  flag on slot.

## Files examined for this skill

| file | lines | depth |
|---|---|---|
| `source/src/backend/replication/README` | 1-76 | full |
| `source/src/backend/replication/walsender.c` | 1-120 | header |
| `source/src/backend/replication/walreceiver.c` | 1-80 | header |
| `source/src/backend/replication/slot.c` | 1-100 | header |
| `source/src/include/replication/slot.h` | 1-200 | partial |
| `source/src/backend/replication/syncrep.c` | 1-80 | header |
| `source/src/backend/replication/logical/decode.c` | 1-80 | header |
| `source/src/backend/replication/logical/reorderbuffer.c` | 1-120 | header |
| `source/src/backend/replication/logical/logical.c` | 1-80 | header |
| `source/src/backend/replication/logical/worker.c` | 1-80 | header |
| `source/src/backend/replication/logical/tablesync.c` | 1-80 | header |
| `source/src/backend/replication/logical/launcher.c` | 1-60 | header |
| `source/src/backend/replication/logical/conflict.c` | 1-60 | header |
| `source/src/backend/replication/repl_gram.y` | grep | command surface |
| `source/src/include/replication/output_plugin.h` | grep | callback contract |
