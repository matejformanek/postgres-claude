---
source_url: https://www.postgresql.org/docs/current/app-pgrecvlogical.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: streaming-replication-clients (2026-06-29 refill)
---

# pg_recvlogical — control and stream a LOGICAL replication slot

`pg_recvlogical` is the logical counterpart to `pg_receivewal`: it connects in
*logical* replication mode, binds a logical slot to an **output plugin**, and
streams the plugin's **decoded** change stream to a file or stdout. `[from-docs]`

## Non-obvious claims

- **Logical decoding is database-specific.** A logical slot is bound to exactly
  one database, so `-d`/`--dbname` is required (unlike instance-wide physical
  replication), and the server needs `wal_level=logical`. `[from-docs]`
- **The output plugin is bound at slot-creation time and is immutable.**
  `-P`/`--plugin` (e.g. `test_decoding`, `pgoutput`) is mandatory with
  `--create-slot` and has **no effect** if the slot already exists. `[from-docs]`
- **Three mutually exclusive actions:** `--create-slot`, `--start`,
  `--drop-slot`. `--create-slot --start` together create-then-stream.
  `[from-docs]`
- **It consumes; there's no peek.** Unlike the SQL `pg_logical_slot_peek_changes`
  / `pg_logical_slot_get_changes` pair, the CLI only consumes (advances the slot)
  — to inspect without consuming you must use the SQL peek function. `[from-docs]`
- **SIGHUP rotates the output file** (close current `-f`, reopen) — the log-
  rotation hook for long-running capture. SIGINT/SIGTERM exit 0. `[from-docs]`

## Options

`-S`/`--slot` (required, all actions); `-d`/`--dbname` (required for
create/start); `-P`/`--plugin` (create only); `-f`/`--file` (`-` = stdout;
required for `--start`); `-o`/`--option=name[=value]` (pass options to the
plugin, e.g. `-o skip_empty_xacts=on`); `-F`/`--fsync-interval`;
`-I`/`--startpos=LSN` + `-E`/`--endpos=LSN` (start mode); `--if-not-exists`;
`--enable-two-phase` (decode prepared xacts); `--enable-failover` (allow slot
sync to standbys); `-n`/`--no-loop`; `-s`/`--status-interval`; `-v`/`--verbose`.
`[from-docs]`

## Slot / plugin / LSN model

Slot creation permanently binds the slot to its plugin; streaming feeds WAL
through the plugin to produce decoded output; LSN confirmations are reported
lazily as data arrives and on clean exit (this is what advances `confirmed_flush`
and lets the server release WAL). `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/logicaldecoding-explanation.md]]`,
  `[[knowledge/docs-distilled/logicaldecoding-output-plugin.md]]`,
  `[[knowledge/docs-distilled/logicaldecoding-walsender.md]]` — the decoding
  concepts, plugin callback API, and the streaming-replication-protocol path
  this CLI drives.
- `[[knowledge/docs-distilled/logicaldecoding-sql.md]]` — the `pg_logical_slot_*`
  SQL interface (peek/get) this CLI parallels (consume-only).
- `[[knowledge/docs-distilled/test-decoding.md]]` — the canonical example plugin.
- `[[knowledge/docs-distilled/app-pgreceivewal.md]]` — the physical counterpart.
- Skill: `replication-overview`.
