# `src/backend/replication/logical/tablesync.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1715
- **Source:** `source/src/backend/replication/logical/tablesync.c`

## Purpose

Initial table data synchronization for logical replication. Each table
gets its own short-lived **tablesync worker** that COPYs the initial data
under a snapshot exported by the publisher, then catches up to the
apply-worker's stream position and exits. Parallelism by table → faster
initial sync, and avoids holding xmin/LSN globally over a long initial
copy. [from-comment] (`tablesync.c:1-28`)

## State machine (per (subid, relid))

`INIT → DATASYNC → FINISHEDCOPY → SYNCWAIT → CATCHUP → SYNCDONE → READY`.
The first three live in `pg_subscription_rel`; SYNCWAIT and CATCHUP are
in-memory only. After SYNCDONE the apply worker is responsible for
flipping to READY once it reaches the synced LSN. (`tablesync.c:29-91`)
[from-comment]

## Spine

- `wait_for_table_state_change` (`:142`) — apply worker waits for
  tablesync to flip from CATCHUP → SYNCDONE.
- `wait_for_worker_state_change` (`:191`) — tablesync waits for apply to
  flip SYNCWAIT → CATCHUP.
- `process_syncing_tables_for_apply` — apply-side polling: spawn missing
  workers, advance states.
- `process_syncing_tables_for_sync` — tablesync-side: flips states at
  the right LSN boundary.
- `LogicalRepSyncTableStart` — pre-copy: open temp replication slot on
  publisher (`pg_<suboid>_sync_<relid>_<sysid>`), export snapshot, COPY
  via `copy_table`, change to CATCHUP at FINISHEDCOPY.
- `copy_table` — builds the publisher-side query (`COPY ... TO STDOUT`)
  honoring publication's `publish_via_partition_root` and any
  row-filter / column-list options. Uses copy.c (CopyFrom) on local side.
- `fetch_remote_table_info` — queries publisher's
  `pg_get_publication_tables` SRF and `pg_relation_is_publishable` to
  learn column lists, replica identity, row filters.

## Snapshot exporting

Each tablesync worker creates a temporary logical slot on the publisher
with `CRS_USE_SNAPSHOT` so it inherits the slot-creation snapshot and
can do a consistent COPY. Slot is dropped at SYNCDONE.

## Origin per (sub, rel)

Replication-origin name for tablesync is
`pg_<suboid>_sync_<relid>_<sysid>` so its progress LSN is tracked
independently of the main apply origin. [verified-by-code]

## Glossary

- `MyLogicalRepWorker` — pointer to the LogicalRepWorker shmem slot for
  this worker (`worker_internal.h`).
- `am_tablesync_worker()` — runtime predicate based on the worker-type
  field.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
