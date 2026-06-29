---
source_url: https://www.postgresql.org/docs/current/app-pgcontroldata.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_controldata — dump the `global/pg_control` file

`pg_controldata` prints the cluster-wide control file (`global/pg_control`)
**without a running server**. It is the canonical "what does the cluster think
its state is" probe for recovery debugging and the precondition check
`pg_upgrade` runs. `-D`/`--pgdata` or `$PGDATA` locates the cluster; you must be
the cluster-owning OS user. `[from-docs]`

## Non-obvious claims

- **Version fields gate upgrades.** `pg_control version number` and `Catalog
  version number` must match between source and target for `pg_upgrade`; the
  `Database system identifier` uniquely fingerprints the cluster and prevents
  cross-cluster WAL/basebackup mixups. `[from-docs]`
- **Cluster state is the load-bearing field for the recovery tools.** Possible
  `Database cluster state` values: `starting up`, `shut down`, `shut down in
  recovery`, `shutting down`, `in crash recovery`, `in archive recovery`, `in
  production`. `pg_checksums` and `pg_resetwal` **refuse to run unless this
  reads a cleanly-shut-down state** (or you force it). `[from-docs]`
- **Checkpoint block is what redo starts from.** `Latest checkpoint location`,
  `Latest checkpoint's REDO location` (where replay actually begins — earlier
  than the checkpoint record itself), `REDO WAL file`, `TimeLineID`,
  `PrevTimeLineID`, and `full_page_writes` at checkpoint time. `[from-docs]`
- **Recovery bounds:** `Minimum recovery ending location`, `Backup start
  location`, `Backup end location`, `End-of-backup record required` — the
  fields a base backup sets so a restore knows the consistency point.
  `[from-docs]`
- **`Data page checksum version`** = 0 when checksums are off, nonzero (the
  algorithm version) when on. This is the exact field `pg_checksums -e/-d` and
  `initdb -k` toggle; the backend reads it at startup. `[from-docs]`

## Fields reported (grouped)

- **Identity/version:** pg_control version number; Catalog version number;
  Database system identifier.
- **State/time:** Database cluster state; pg_control last modified.
- **Checkpoint/WAL:** Latest checkpoint location; REDO location; REDO WAL file;
  TimeLineID; PrevTimeLineID; checkpoint full_page_writes; checkpoint time;
  fake LSN counter for unlogged rels; Minimum recovery ending location; Backup
  start/end location; End-of-backup record required.
- **XID/OID state:** NextXID; oldestXID (+ its DB); NextOID; NextMultiXactId;
  NextMultiOffset; oldestActiveXID; oldestMultiXid (+ its DB);
  oldestCommitTsXid / newestCommitTsXid.
- **GUC-derived limits baked into WAL:** wal_level; wal_log_hints;
  max_connections; max_worker_processes; max_wal_senders; max_prepared_xacts;
  max_locks_per_xact; track_commit_timestamp. (A standby's settings must be
  ≥ the primary's for several of these.)
- **On-disk format constants:** Maximum data alignment; Database block size;
  Blocks per segment of large relation; WAL block size; Bytes per WAL segment;
  Maximum length of identifiers; Maximum columns in an index; Maximum size of a
  large-object chunk; Date/time type storage (float8 vs integer); Float8
  argument passing; **Data page checksum version**.

## Links into corpus

- `[[knowledge/docs-distilled/wal-internals.md]]` — the checkpoint/REDO LSN
  semantics these fields expose.
- `[[knowledge/docs-distilled/app-pgresetwal.md]]` — the write side: pg_resetwal
  rewrites exactly these pg_control fields when it's unreadable.
- `[[knowledge/docs-distilled/app-pgchecksums.md]]` — reads/writes the
  `Data page checksum version` field shown here.
- `[[knowledge/docs-distilled/two-phase.md]]`,
  `[[knowledge/docs-distilled/transaction-id.md]]` — NextXID/oldestXID/multixact
  counters reported here.
- Skill: `wal-and-xlog`, `debugging`, `replication-overview`.
