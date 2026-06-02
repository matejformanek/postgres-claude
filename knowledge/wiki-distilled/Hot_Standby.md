---
source_url: https://wiki.postgresql.org/wiki/Hot_Standby
also_fetched:
  - https://www.postgresql.org/docs/current/hot-standby.html
fetched_at: 2026-06-02T11:19:25Z
wiki_last_edited: 2016-06-30T15:02Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: wiki page is from 2016 — still says `wal_level = hot_standby`
  (a value renamed to `replica` in PG 9.6) and `standby_mode='on'` in
  recovery.conf (removed in PG 12, folded into standby.signal). It omits
  recovery conflicts, the standby-feedback GUCs, and the running-xacts /
  KnownAssignedXids machinery. Supplemented below from the official
  hot-standby.html (§27.4), all tagged [from-docs].
---

# Wiki distilled — Hot Standby

Running **read-only queries on a standby while it continuously replays WAL**.
The wiki page is correct in outline but ~10 years stale on parameter names and
silent on the hard parts (recovery conflicts, feedback, snapshot bootstrap).
Replication companion: `knowledge/architecture/replication.md`.

## What the wiki page says (2016)

- **Hot Standby = "run queries on a database currently performing archive
  recovery"** — read-only query access on a replica. [from-wiki]
- **It augments streaming replication but doesn't depend on it** — "has minimal
  interaction with it." Hot Standby works off WAL replay whether the WAL arrives
  by streaming or by archive `restore_command`. [from-wiki]
- **Config sketch it gives:** `wal_level = hot_standby`, `archive_mode = on`,
  `archive_command`, `max_wal_senders` on the primary; `hot_standby = on` and
  `standby_mode = 'on'` + `restore_command` on the standby. [from-wiki]
- **Diagnostics it gives:** `SELECT pg_is_in_recovery();` (true on a standby) and
  `SELECT txid_current_snapshot();`. [from-wiki]

### What's stale in that sketch

- **`wal_level = hot_standby` was renamed `replica` in PG 9.6** — the old value
  is still accepted as an alias but the canonical setting is `replica` (or
  `logical`). [from-docs]
- **`standby_mode = 'on'` / `recovery.conf` were removed in PG 12.** A standby is
  now signalled by a `standby.signal` file in the data directory; recovery
  parameters moved into `postgresql.conf`. [from-docs]
- **`txid_current_snapshot()` is superseded by `pg_current_snapshot()`** (the
  `txid_*` family is deprecated in favour of the full-64-bit `xid8` `pg_*`
  functions). [from-docs]

## What the wiki omits — corpus + docs supplement (§27.4)

### Recovery conflicts — the defining hard problem

WAL replay on the standby can need to do something that is incompatible with an
in-flight read-only query. When the delay budget is exhausted the **query is
cancelled**, not the replay:

```
ERROR:  canceling statement due to conflict with recovery
```

The documented conflict causes: [from-docs]

1. **`ACCESS EXCLUSIVE` locks replayed from the primary** — `DROP TABLE`,
   `TRUNCATE`, many `ALTER TABLE` forms.
2. **Early cleanup of still-needed row versions** — a `VACUUM`/HOT-prune cleanup
   record removes tuples a standby snapshot can still see ("User query might have
   needed to see row versions that must be removed"). This is the most common and
   most annoying one.
3. **Visibility-map all-visible updates** for pages whose rows a standby query
   still needs.
4. **Dropping a tablespace** the standby is using for temp/work files.
5. **Dropping a database** a standby session is connected to (that session is
   evicted).

A buffer-pin deadlock and replay of a B-tree page deletion are additional
lower-level cases. [from-docs]

### The delay knobs (and the trap)

| GUC | Default | Meaning |
|---|---|---|
| `hot_standby` | `on` | accept read-only connections during recovery [from-docs] |
| `max_standby_streaming_delay` | `30s` | grace before cancelling a query that blocks *streamed* WAL replay [from-docs] |
| `max_standby_archive_delay` | `30s` | same, for WAL read from the *archive* [from-docs] |
| `hot_standby_feedback` | `off` | report standby's oldest xmin upstream (below) [from-docs] |

- **The delay is a total budget for replay lag, not per-query.** Once a query has
  caused that many seconds of cumulative replay delay, it's eligible for
  cancellation; a single long query spends the whole budget for everyone behind
  it. Setting `-1` waits forever (unbounded replication lag). [from-docs]

### `hot_standby_feedback` — trade cancellations for bloat

- When `on`, the standby continuously reports its **oldest visible xmin** back up
  the replication link; the primary then **declines to vacuum away row versions
  the standby still needs**, eliminating the cleanup-conflict class (#2 above).
  [from-docs]
- **Cost:** dead tuples persist longer on the **primary** → more bloat there. It
  also doesn't help against `ACCESS EXCLUSIVE`/DDL conflicts. [from-docs]

### What you cannot do on a standby

`transaction_read_only` is forced **true** and cannot be turned off, so any write
path is rejected: all write DML/DDL (`INSERT`/`UPDATE`/`DELETE`/`MERGE`/`COPY
FROM`/`TRUNCATE`/`CREATE`/`DROP`/`ALTER`), sequence `nextval()`/`setval()`,
`LISTEN`/`NOTIFY`/`UNLISTEN`, two-phase commit (`PREPARE TRANSACTION`/`COMMIT
PREPARED`/`ROLLBACK PREPARED`), `SELECT … FOR UPDATE/SHARE`, `LOCK TABLE` above
`ROW EXCLUSIVE`, temp-table creation, and explicit `BEGIN READ WRITE`. Autovacuum
is inactive during recovery. [from-docs]

### How the standby bootstraps a usable snapshot — KnownAssignedXids

- A standby **cannot accept connections until it reaches a *consistent recovery
  state*** — it must know the full set of write transactions that were in
  progress on the primary, or its snapshots would be wrong. [from-docs]
- The primary periodically emits **`XLOG_RUNNING_XACTS`** records (at each
  checkpoint and on demand); replaying them lets the standby build
  **`KnownAssignedXids`**, the in-recovery analogue of the primary's PGPROC xid
  array. Only once this is populated can `GetSnapshotData` on the standby produce
  safe snapshots and the postmaster log:
  `LOG: consistent recovery state reached` →
  `LOG: database system is ready to accept read-only connections`. [from-docs]
  [mechanism: knowledge/files/src/backend/storage/ipc/standby.c.md +
  knowledge/files/src/backend/storage/ipc/procarray.c.md — KnownAssignedXids
  lives in procarray.c; standby.c handles the running-xacts records and recovery
  conflict signalling]
- **Caveat:** a primary transaction with **>64 subtransactions** overflows the
  per-backend subxid cache, which delays the standby reaching a consistent state
  until such transactions complete. [from-docs]

### Parameter-sizing rule

The standby's `max_connections`, `max_prepared_transactions`,
`max_locks_per_transaction`, `max_wal_senders`, `max_worker_processes` must each
be **≥ the primary's** value (these size shared-memory structures that track
primary state). If not, recovery pauses with
`WARNING: hot standby is not possible because of insufficient parameter
settings`. [from-docs]

## Why it matters operationally

- The central tension of read-replica usage is **query-cancellation vs.
  replication-lag vs. primary-bloat**: raise `max_standby_*_delay` to cancel
  fewer queries (at the cost of lag), or enable `hot_standby_feedback` to cancel
  fewer queries (at the cost of primary bloat). There's no free option. [inferred
  — direct consequence of the §27.4 mechanics above]
- Hint bits are still written on the standby even though it's read-only — replay
  and visibility checks dirty pages just like on a primary. [from-docs]
  (See `knowledge/wiki-distilled/Hint_Bits.md` for the hint-bit mechanism.)

## Links into corpus

- [[knowledge/architecture/replication.md]] — physical streaming + the walsender/
  walreceiver pipeline Hot Standby reads its WAL from.
- [[knowledge/files/src/backend/storage/ipc/standby.c.md]] — recovery-conflict
  resolution and the running-xacts handling on the standby side.
- [[knowledge/files/src/backend/storage/ipc/procarray.c.md]] — `KnownAssignedXids`
  and standby snapshot construction.
- [[knowledge/data-structures/pgproc-fields.md]] — the primary-side PGPROC xid
  fields whose standby mirror is `KnownAssignedXids`.
- [[knowledge/data-structures/snapshot-lifecycle.md]] — how snapshots (the thing
  recovery conflicts protect) are built and what xmin a query exposes upstream.
- [[knowledge/architecture/wal.md]] — `XLOG_RUNNING_XACTS` is one of the record
  types replayed during recovery.

## Confidence note

Wiki-sourced claims are `[from-wiki]` and accurate-but-dated (2016): the
parameter names (`wal_level=hot_standby`, `standby_mode`, `txid_current_snapshot`)
are superseded as noted. Every supplement (recovery conflicts, delay GUCs,
feedback, KnownAssignedXids, parameter sizing) is `[from-docs]` against the
current `hot-standby.html` (§27.4). Code-symbol pointers (`standby.c`,
`procarray.c`, `KnownAssignedXids`) route through the per-file corpus docs; exact
line numbers were not re-verified this run (source tree not mounted in the cloud
routine) — confirm against anchor `4b0bf0788b` on a future file-backfill pass.
