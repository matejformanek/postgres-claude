---
source_url: https://www.postgresql.org/docs/current/warm-standby.html
fetched_at: 2026-07-03T20:47:00Z
anchor_sha: a5422fe3bd7e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Log-Shipping Standby Servers (§26.2)

The physical-replication chapter: a standby in **continuous recovery** that
consumes the primary's WAL either as whole segments (file-based) or as a live
record stream (streaming replication), optionally synchronously. This is the
physical twin of the already-distilled §29 logical-replication family.

## Standby operation + the restore chain

- A server is a standby **iff `standby.signal` exists** in the data dir at start;
  it then stays in recovery, replaying WAL indefinitely instead of stopping at a
  target. [from-docs]
- **File-based** shipping moves entire **16 MB segments** one at a time (data-loss
  window = up to one unshipped segment); **record-based** (streaming) ships WAL at
  record granularity for a far smaller window. [from-docs]
- Standby WAL-source priority: **(1) `restore_command` from archive → (2) files
  dropped in `pg_wal/` → (3) streaming via `primary_conninfo`**; when streaming
  breaks it loops back to the archive, and vice-versa. [from-docs]
- `restore_command` must **fail fast when the file is absent** — a command that
  blocks stalls the whole standby. [from-docs]

## Streaming replication — process model + setup

- With `primary_conninfo` set, the standby spawns a **`walreceiver`** and the
  primary a matching **`walsender`**; they speak the replication sub-protocol over
  one TCP connection. [from-docs] — see idioms
  `knowledge/idioms/wal-receiver-loop.md`, `.../walsender-state-machine.md`.
- Primary prerequisites: **`max_wal_senders` > 0**, a `pg_hba.conf` line with the
  **`replication`** pseudo-database, and a role with the **`REPLICATION`**
  attribute (or superuser). `REPLICATION` is powerful but **cannot modify data** —
  unlike `SUPERUSER`. Example: `host replication foo 192.168.1.100/32
  scram-sha-256`. [from-docs]
- **`wal_receiver_status_interval`** sets how often the standby sends
  write/flush/apply feedback to the primary; **`0` disables** it, which breaks
  synchronous confirmation and lag reporting. [from-docs]

## Replication slots — automated WAL retention

- Without slots (or `wal_keep_size`), the primary may **recycle segments before
  the standby reads them**, forcing a standby rebuild. [from-docs]
- **`pg_create_physical_replication_slot('name')`** + **`primary_slot_name`** on
  the standby makes the primary retain WAL (and, with `hot_standby_feedback`,
  hold back cleanup) until the standby has consumed it — even while the standby is
  **disconnected**. State is in **`pg_replication_slots`**. [from-docs]
- The flip side: a slot for a dead/slow standby can grow `pg_wal/` **without
  bound**; **`max_slot_wal_keep_size`** caps slot-held WAL (past the cap the slot
  is **invalidated**, trading the standby for disk safety). [from-docs] — see
  `knowledge/idioms/replication-slot-advance.md`.

## Cascading, synchronous, archiving-in-standby

- **Cascading:** a standby with `max_wal_senders` + `hot_standby` can feed
  downstream standbys, offloading the primary; it relays both streamed and
  archive-restored WAL, so downstream keeps flowing even if the upstream link
  drops (as long as archive WAL is reachable). [from-docs]
- **Synchronous replication:** empty `synchronous_standby_names` ⇒ **async**
  (commit returns before the standby has it). A non-empty value makes commit wait
  for standby confirmation. Per-transaction **`synchronous_commit`** durability
  ladder: **`remote_write`** (standby OS buffer) < **`on`** (standby disk,
  default) < **`remote_apply`** (standby has *replayed* → visible to standby
  reads). [from-docs]
- Quorum vs priority: **`FIRST N (s1,s2,s3)`** waits for the N highest-priority
  named standbys; **`ANY N (s1,s2,s3)`** waits for any N (quorum). [from-docs]
- A standby only becomes eligible as synchronous once it reaches the
  **`streaming`** state (it starts in **`catchup`**); state is the `state` /
  `sync_state` columns of **`pg_stat_replication`**. [from-docs]
- **`archive_mode = always`** runs the archiver on the standby too (every received
  segment is archived); plain **`on`** archives only after promotion — so segments
  received *during* standby operation are never archived under `on`. [from-docs]

## Monitoring LSNs

- Lag ≈ **`pg_current_wal_lsn()`** (primary) − **`pg_last_wal_receive_lsn()`**
  (standby). `pg_stat_replication` exposes the primary-side
  **`sent_lsn` / `write_lsn` / `flush_lsn` / `replay_lsn`** per standby;
  **`pg_stat_wal_receiver`** exposes the receiver side. A large
  `flushed − replayed` gap means WAL arrives faster than it replays (a hot-standby
  conflict-delay symptom). [from-docs]

## Links into corpus

- `knowledge/docs-distilled/hot-standby.md` — running read-only queries on this
  standby + the recovery-conflict cost of a slow replay.
- `knowledge/docs-distilled/warm-standby-failover.md` — promoting it.
- `knowledge/docs-distilled/continuous-archiving.md` — the `restore_command` +
  `standby.signal` machinery, run to a target instead of continuously.
- `knowledge/docs-distilled/runtime-config-replication.md` — the full GUC surface
  (`synchronous_standby_names`, `wal_keep_size`, `hot_standby_feedback`, …).
- `knowledge/docs-distilled/app-pgbasebackup.md`,
  `.../app-pgreceivewal.md`, `.../logical-replication-architecture.md`.
- `knowledge/idioms/wal-receiver-loop.md`,
  `.../walsender-state-machine.md`, `.../replication-slot-advance.md`;
  `knowledge/subsystems/replication.md`.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/warm-standby.html (PG18).
- `walreceiver`/`walsender` process + slot mechanics are code in
  `source/src/backend/replication/walreceiver.c`,
  `.../walsender.c`, `.../slot.c` at anchor `a5422fe3bd7e` — cross-referenced,
  not line-verified this run.
