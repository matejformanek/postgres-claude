# Tablesync initial copy — per-table COPY-based bootstrap

Before normal apply-streaming begins on a SUBSCRIPTION, every
published table on the subscriber needs its **initial data
snapshot**. A short-lived **tablesync worker** is spawned per
table; it acquires the publisher's slot-creation snapshot,
runs a COPY FROM PUBLISHER into the local table, and then
catches up to the apply worker's position via streaming the
incremental WAL. Once caught up, the tablesync worker exits
and the main apply worker takes over.

Anchors:
- `source/src/backend/replication/logical/tablesync.c:1252` —
  LogicalRepSyncTableStart [verified-by-code]
- `source/src/backend/replication/logical/tablesync.c:1075` —
  copy_table [verified-by-code]
- `knowledge/idioms/apply-worker-loop.md` — companion
- `knowledge/idioms/logical-decoding-snapshot.md` — companion
  (the slot's exported snapshot)
- `.claude/skills/replication-overview/SKILL.md` — companion

## Per-table state machine

[from `tablesync.c`]

```
INIT
  ↓ launcher schedules worker
SYNCWAIT   ← waiting for apply worker to set start position
  ↓ apply worker signals "go"
CATCHUP    ← apply already-streamed changes to bring up
  ↓ caught up
SYNCDONE   ← table is ready for normal apply
```

Per-table state stored in `pg_subscription_rel.srsubstate`
(values: 'i' INIT, 's' SYNCWAIT, 'c' CATCHUP, 'd' SYNCDONE).
Inspectable via:

```sql
SELECT srsubid, srrelid, srsubstate, srsublsn
FROM pg_subscription_rel;
```

## Tablesync worker startup

[verified-by-code `tablesync.c:1252`]

```c
char *
LogicalRepSyncTableStart(XLogRecPtr *origin_startpos);
```

The worker:
1. Creates a temporary replication slot on the publisher
   (`tap_%u_%u` name).
2. The slot creation EXPORTS a snapshot (via
   `SnapBuildExportSnapshot`).
3. The worker sets its local backend's snapshot to the
   exported one via `SET TRANSACTION SNAPSHOT`.
4. Runs `COPY FROM PUBLISHER` into the local table under
   that snapshot.
5. Updates `srsubstate` to 'c' (CATCHUP).
6. Streams WAL from the slot's start LSN, applying changes
   until caught up to the apply worker's position.

The exported snapshot ensures the COPY sees exactly the data
that was committed before the slot's LSN.

## copy_table — the bulk data load

[verified-by-code `tablesync.c:1075`]

```c
static void
copy_table(Relation rel);
```

Issues:
```sql
COPY <schema>.<table> ( <columns> )
TO STDOUT WITH (FORMAT binary)
```

on the publisher, then `COPY <table> FROM STDIN WITH (FORMAT
binary)` on the subscriber. The data flows through the libpq
COPY-IN protocol, batched in libpq-default-sized chunks.

For partition tables: the published relation list determines
what gets copied (parent or leaf partitions).

## Why tablesync needs a separate slot

The main apply worker's slot is at the SUBSCRIPTION's
catalog_xmin / restart_lsn — not at the per-table point. The
tablesync worker needs its OWN slot at the per-table start
LSN so that:
- Initial COPY data is consistent with the slot's snapshot.
- Subsequent WAL streaming starts exactly where the COPY left
  off.

After SYNCDONE: the per-table slot is dropped. The main
subscription slot continues to track overall progress.

## Catchup phase

Once COPY finishes, the tablesync worker streams WAL from the
publisher (continuing on the SAME slot it created for the
COPY snapshot) until it reaches the apply worker's current
position.

During catchup:
- Other tables' changes in the WAL are SKIPPED (they don't
  apply to this worker's table).
- This-table changes are applied via the same
  `apply_handle_*` family used by the main apply worker.
- Progress recorded via the worker's replication origin.

When the worker's LSN ≥ the apply worker's LSN: SYNCDONE.

## Handoff to apply worker

After SYNCDONE:
1. Tablesync worker drops its temporary slot.
2. Updates `srsubstate` to 'r' (READY) or 'd' (SYNCDONE
   depending on PG version).
3. Worker exits.
4. The main apply worker, when next processing a change for
   this table, sees `srsubstate = ready` and applies normally.

Until then, the apply worker SKIPS changes for the still-
syncing table (the tablesync will catch them).

## Failure semantics

- **COPY fails**: worker exits; launcher restarts it with
  exponential backoff. `srsubstate` goes back to 'i'.
- **Apply during catchup fails**: same — restart, retry from
  COPY.
- **Subscription dropped during sync**: workers receive
  SIGTERM; slots are dropped.

The temporary per-table slot must be cleaned up on success
OR failure (else slot leak).

## Concurrency limits

```sql
ALTER SUBSCRIPTION s SET (max_sync_workers_per_subscription = 4);
```

Caps how many tablesync workers can run simultaneously per
subscription. Trade-off: more workers = faster initial sync
but more publisher load + slot count.

Default: 2.

## Common review-time concerns

- **Per-table slots are temporary** but must be cleaned up
  carefully on failure (slot leak risk).
- **Snapshot export window** is narrow — subscriber must
  acquire promptly after slot creation.
- **Catchup applies via apply_handle_*** — same code path as
  main worker; conflicts go to conflict-resolution.
- **Skip-table while syncing** in main apply worker is by
  state check; performance-sensitive.
- **Parallel sync limit** — too many = publisher load
  surge.
- **Failed tablesync = SUBSCRIPTION stays in incomplete
  state**; needs manual intervention if persistent.

## Invariants

- **[INV-1]** One short-lived tablesync worker per syncing
  table.
- **[INV-2]** Worker creates a TEMP slot with snapshot
  export.
- **[INV-3]** COPY runs under the exported snapshot.
- **[INV-4]** Catchup applies WAL from slot's start LSN.
- **[INV-5]** SYNCDONE triggers handoff to main apply
  worker; temp slot dropped.

## Useful greps

- The main flow:
  `grep -n 'LogicalRepSyncTableStart\|copy_table\|process_syncing_tables' source/src/backend/replication/logical/tablesync.c | head -10`
- State enum:
  `grep -RIn 'SUBREL_STATE_INIT\|SUBREL_STATE_SYNCWAIT\|SUBREL_STATE_CATCHUP\|SUBREL_STATE_READY' source/src/include | head -10`
- Launcher coordination:
  `grep -n 'AtEOXact_ApplyLauncher\|logicalrep_sync_worker' source/src/backend/replication/logical/launcher.c | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/tablesync.c`](../files/src/backend/replication/logical/tablesync.c.md) | 1075 | copy_table |
| [`src/backend/replication/logical/tablesync.c`](../files/src/backend/replication/logical/tablesync.c.md) | 1252 | LogicalRepSyncTableStart |
| [`src/backend/replication/logical/tablesync.c`](../files/src/backend/replication/logical/tablesync.c.md) | — | full module |
| [`src/include/catalog/pg_subscription_rel.h`](../files/src/include/catalog/pg_subscription_rel.h.md) | — | per-table state catalog |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/apply-worker-loop.md` — main apply
  worker that consumes the handoff.
- `knowledge/idioms/logical-decoding-snapshot.md` —
  SnapBuildExportSnapshot provides the COPY snapshot.
- `knowledge/idioms/replication-slot-advance.md` —
  per-table temp slots.
- `knowledge/idioms/apply-conflict-resolution.md` —
  conflicts can occur during catchup too.
- `knowledge/idioms/background-worker-startup.md` —
  tablesync workers are bgworkers.
- `knowledge/idioms/replication-origin-tracking.md` —
  per-worker origin during sync.
- `knowledge/subsystems/replication.md` — replication.
- `.claude/skills/replication-overview/SKILL.md` —
  companion.
- `source/src/backend/replication/logical/tablesync.c` —
  full module.
- `source/src/include/catalog/pg_subscription_rel.h` —
  per-table state catalog.
