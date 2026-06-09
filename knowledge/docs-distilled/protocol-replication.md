---
source_url: https://www.postgresql.org/docs/current/protocol-replication.html
fetched_at: 2026-06-09T20:48:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Streaming Replication Protocol

The wire protocol a walsender speaks. Companion to the `replication` subsystem
synthesis; the parser for these commands is the bespoke grammar in
`src/backend/replication/repl_gram.y`, driven by `walsender.c`.

## Entering replication mode

- A connection becomes a walsender by passing the **`replication`** parameter in
  the startup packet: [from-docs]
  - **`replication=true`** (or `on`/`yes`/`1`) → **physical** walsender mode;
    only replication commands are accepted, not arbitrary SQL.
  - **`replication=database`** → **logical** walsender mode, bound to the
    `dbname` database; *both* replication commands **and** ordinary SQL run.
- Either way **only the simple query protocol** is usable in this mode. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/replication/walsender.c.md]]]

## The replication commands

- **`IDENTIFY_SYSTEM`** → one row: `systemid` (text), `timeline` (int8),
  `xlogpos` (text, current flush LSN), `dbname` (text or null). [from-docs]
- **`CREATE_REPLICATION_SLOT name [TEMPORARY] {PHYSICAL | LOGICAL plugin}
  [(options)]`** → returns `slot_name`, `consistent_point`, `snapshot_name`,
  `output_plugin`. Options include `TWO_PHASE`, `RESERVE_WAL` (physical),
  `SNAPSHOT {'export'|'use'|'nothing'}`, and **`FAILOVER`** (sync the logical
  slot to standbys). [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/replication/slotfuncs.c.md]]]
- **Physical:** `START_REPLICATION [SLOT name] [PHYSICAL] XXX/XXX [TIMELINE
  tli]` — stream raw WAL from an LSN on a timeline. [from-docs]
- **Logical:** `START_REPLICATION SLOT name LOGICAL XXX/XXX [(opts)]` — streams
  from `max(requested LSN, slot.confirmed_flush_lsn)`, decoded by the slot's
  output plugin (e.g. `pgoutput`). [from-docs]

## CopyBoth + the four streaming messages

Both `START_REPLICATION` forms answer with **`CopyBothResponse`**, opening a
bidirectional COPY in which these `CopyData` sub-messages flow: [from-docs]

- **`XLogData` (`'w'`, B→F):** `Int64` WAL start, `Int64` server WAL end,
  `Int64` server clock (µs since 2000-01-01), then the WAL bytes. **A single WAL
  record is never split across two `XLogData` messages.** [from-docs]
- **Primary keepalive (`'k'`, B→F):** server WAL end + clock + a
  *reply-requested* flag byte (1 ⇒ client must reply now to dodge timeout). [from-docs]
- **Standby status update (`'r'`, F→B):** three LSNs — last byte+1
  **written**, **flushed**, **applied** — plus client clock + reply-request flag.
  This is what drives `pg_stat_replication.{write,flush,replay}_lsn` and
  synchronous-commit release. [from-docs]
  [cross: [[knowledge/files/src/backend/replication/syncrep.c.md]]]
- **Hot standby feedback (`'h'`, F→B):** client clock, global `xmin` (+epoch),
  and lowest slot `catalog_xmin` (+epoch) — lets the primary hold back vacuum so
  standby queries don't see removed rows. Ties to `hot_standby_feedback`. [from-docs]

The COPY ends (CommandComplete) on replication completion or a timeline switch. [from-docs]

## Physical vs logical at a glance

| | physical | logical |
|---|---|---|
| startup param | `replication=true` | `replication=database` |
| payload | raw WAL bytes | plugin-decoded changes |
| output plugin | none | required (`pgoutput`, …) |
| snapshot export | n/a | via `SNAPSHOT` option |

## Links into corpus
- [[knowledge/subsystems/replication.md]] — walsender/walreceiver/slot synthesis.
- [[knowledge/architecture/replication.md]] — physical vs logical narrative.
- [[knowledge/files/src/backend/replication/walsender.c.md]] — command dispatch + XLogData loop.
- [[knowledge/files/src/backend/replication/walreceiver.c.md]] — the standby side sending `'r'`/`'h'`.
- [[knowledge/files/src/backend/replication/repl_gram.y.md]] — the replication-command grammar.
- [[knowledge/files/src/backend/replication/pgoutput/pgoutput.c.md]] — the built-in logical output plugin.
- [[knowledge/docs-distilled/runtime-config-replication.md]] — the GUC companion.
- Skill: `replication-overview` — operational orientation across all flavors.

## Gaps / follow-ups
- The *contents* of logical `XLogData` (Begin/Commit/Insert/Update tuple
  messages) are a separate `pgoutput`-specific format, not covered here.
- `TIMELINE_HISTORY`, `READ_REPLICATION_SLOT`, `DROP_REPLICATION_SLOT`,
  `BASE_BACKUP` commands exist on the same protocol but are out of scope of this distill.
