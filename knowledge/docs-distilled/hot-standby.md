---
source_url: https://www.postgresql.org/docs/current/hot-standby.html
fetched_at: 2026-07-03T20:47:00Z
anchor_sha: a5422fe3bd7e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Hot Standby (§26.4)

Read-only queries **during** recovery. The hard part isn't serving reads — it's
the tension between a query's snapshot and the WAL replay stream removing rows or
taking locks that query still needs. That tension is the **recovery-conflict**
mechanism, the meatiest internals in the chapter.

## What it is

- **`hot_standby = on`** (standby) lets the server accept **strictly read-only**
  connections once recovery reaches a **consistent state**. [from-docs]
- Consistency is reached when a **running-xacts** WAL record lets the standby
  build a valid snapshot (tracked via **KnownAssignedXids**; `pg_control`'s
  `minRecoveryPoint` bounds it). The server logs
  **`LOG: consistent recovery state reached`** before opening for reads.
  [from-docs / from-comment] — see idiom `knowledge/idioms/snapshot-acquisition.md`.
- Data is **eventually consistent**: the same query on primary vs standby can
  differ until the relevant commit record is replayed on the standby. [from-docs]
- **`SHOW in_hot_standby`** (PG14+) tells a session it's on a hot standby; older
  clients probed `transaction_read_only`. [from-docs]

## Recovery conflicts — the five categories

WAL replay can collide with an in-flight standby query. The hard-conflict types:

1. **Snapshot / cleanup** — a VACUUM cleanup record removes a row tuple a running
   query's snapshot can still see. [from-docs]
2. **Buffer pin** — replay needs to clean a page the query holds a pin on.
   [from-docs]
3. **Lock** — replay of an **ACCESS EXCLUSIVE** lock (DDL / explicit LOCK on the
   primary) conflicts with the query's table access. [from-docs]
4. **Tablespace drop** — a dropped tablespace conflicts with a query's temp work
   files living there. [from-docs]
5. **Database drop** — a `DROP DATABASE` conflicts with sessions connected to it
   (those sessions are terminated). Deadlock between replay and a query is
   detected and one side is cancelled. [from-docs]

## Resolving conflicts — delay vs cancel

- The standby either **delays WAL replay** to let the query finish, or **cancels
  the query** once the grace period is exceeded. Two separate budgets, measured
  from when the WAL data was **received** on the standby:
  **`max_standby_streaming_delay`** (WAL via streaming) and
  **`max_standby_archive_delay`** (WAL via `restore_command`). [from-docs]
- **`-1` = wait forever** (never cancel; replay lag can grow without bound).
  Setting these high favors queries and grows lag; low favors freshness and
  cancels queries. [from-docs]
- **`hot_standby_feedback = on`** makes the standby report its **oldest xmin** to
  the primary, so the primary's VACUUM won't remove rows the standby still needs —
  eliminating most snapshot conflicts at the cost of **bloat on the primary**
  (and it does nothing across a failover or for WAL already generated).
  [from-docs] — see idiom `knowledge/idioms/xmin-horizon-management.md`.
- **`pg_stat_database_conflicts`** counts cancellations by type:
  **`confl_tablespace` / `confl_lock` / `confl_snapshot` / `confl_bufferpin` /
  `confl_deadlock` / `confl_active_logicalslot`**. [from-docs]

## What you can't do on a standby

- No DML (`INSERT`/`UPDATE`/`DELETE`/`MERGE`/`COPY FROM`/`TRUNCATE`), no DDL, no
  **`SELECT … FOR SHARE/UPDATE`** (row locks write xmax), no 2PC
  (`PREPARE/COMMIT/ROLLBACK PREPARED`), no sequence advance (`nextval`/`setval`),
  no `LISTEN`/`NOTIFY`. [from-docs]
- Explicit `LOCK` limited to **ACCESS SHARE / ROW SHARE / ROW EXCLUSIVE**;
  ACCESS EXCLUSIVE (and short-form `LOCK`, which requests it) is forbidden.
  [from-docs]
- **Temp tables are forbidden** during recovery — writing their rows needs a real
  XID, which a recovering server can't assign. [from-docs]
- But the standby is **not** truly read-only at the storage layer: it still writes
  **hint bits**, temp sort spill files, and rebuilds relcache — user transactions
  are read-only, the process is not. [from-docs] — see idiom
  `knowledge/idioms/hint-bits-setbufferdirty.md`.

## Administrator's overview — shmem parameter coupling

- These standby GUCs must be **≥ the primary's** or hot standby refuses to start:
  **`max_connections`, `max_prepared_transactions`, `max_locks_per_transaction`,
  `max_wal_senders`, `max_worker_processes`**. [from-docs]
- Their values are **tracked in WAL**; if the primary later raises one above the
  standby's value, the standby logs a **WARNING and pauses recovery** until you
  raise the standby value and restart. Order of change matters: raise on standby
  first, lower on standby last. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/warm-standby.md` — the streaming/restore machinery
  that feeds this standby; `flushed − replayed` lag is the conflict-delay
  symptom.
- `knowledge/docs-distilled/mvcc.md` — the snapshot visibility rules the
  snapshot/cleanup conflict is defined against.
- `knowledge/docs-distilled/runtime-config-replication.md` — the
  `max_standby_*_delay` / `hot_standby_feedback` GUC surface.
- `knowledge/idioms/xmin-horizon-management.md`,
  `.../snapshot-acquisition.md`, `.../hint-bits-setbufferdirty.md`;
  `knowledge/subsystems/replication.md`, `knowledge/subsystems/storage-buffer.md`.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/hot-standby.html (PG18).
- Consistency-point internals (running-xacts record, KnownAssignedXids,
  minRecoveryPoint) are code in `source/src/backend/storage/ipc/procarray.c`
  and `.../access/transam/xlog.c` at anchor `a5422fe3bd7e` — cross-referenced,
  not line-verified this run.
