---
source_url: https://www.postgresql.org/docs/current/app-pgreceivewal.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: streaming-replication-clients (2026-06-29 refill)
---

# pg_receivewal — stream raw WAL to disk as a continuous archive

`pg_receivewal` behaves like a standby's walreceiver but **only persists WAL to
disk; it never applies it**. It streams via the replication protocol and writes
standard 16MB segments locally — low-latency continuous archiving for PITR.
`[from-docs]`

## Non-obvious claims

- **Flushes on segment close by default, not per record.** Real-time flushing
  requires `--synchronous`. This matters because to act as a *synchronous*
  standby (matched in `synchronous_standby_names`) it must flush + report
  immediately — without `--synchronous`, feedback only happens on segment close,
  so committing transactions on the primary **block indefinitely** (it looks
  like it never catches up). `[from-docs]`
- **Makes `archive_timeout` unnecessary** — it streams as WAL is generated
  rather than waiting for segment completion. `[from-docs]`
- **Uses the real WAL file conventions:** 16MB segments, `.partial` suffix on
  the in-progress segment; `-Z gzip`/`lz4` adds `.gz`/`.lz4` to *completed*
  segments. `[from-docs]`
- **Use a physical slot (`-S`) or the server may recycle WAL before it's
  archived** — there's no feedback otherwise. With a slot it reports flush
  position so the server retains needed WAL. `[from-docs]`
- **Start-position resolution order:** (1) newest completed segment in `-D` →
  next segment; (2) PG15+ with a slot → `READ_REPLICATION_SLOT` `restart_lsn`;
  (3) fall back to `IDENTIFY_SYSTEM` flush location. `[from-docs]`

## Options

`-D dir` (required); `-S slot` / `--create-slot` / `--drop-slot` /
`--if-not-exists`; `--synchronous`; `-E`/`--endpos=LSN` (stop, exit 0);
`-n`/`--no-loop` (don't retry on error — default retries forever);
`-s`/`--status-interval` (default 10s; 0 disables); `-Z`/`--compress`
(gzip/lz4/none); `--no-sync` (unsafe, incompatible with `--synchronous`);
`-v`/`--verbose`. Exit 0 on SIGINT/SIGTERM. `[from-docs]`

## vs pg_recvlogical

Physical raw WAL segments (uninterpreted) here, vs decoded logical change stream
in `pg_recvlogical`. Physical slot vs logical slot; instance-wide vs
one-database-per-slot. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/app-pgrecvlogical.md]]` — the logical counterpart.
- `[[knowledge/docs-distilled/app-pgbasebackup.md]]` — shares the walsender path;
  `pg_basebackup -X stream` essentially does this concurrently with the backup.
- `[[knowledge/docs-distilled/protocol-replication.md]]`,
  `[[knowledge/docs-distilled/runtime-config-replication.md]]` — replication
  commands + `synchronous_standby_names` context.
- Skill: `replication-overview`, `wal-and-xlog`.
