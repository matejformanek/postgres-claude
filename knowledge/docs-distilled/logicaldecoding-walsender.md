---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-walsender.html
fetched_at: 2026-06-19T18:50:00Z
anchor_sha: bdae2c20e88d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Streaming Replication Protocol Interface (logical-decoding ch. 49.3)

The walsender path to logical decoding — the streaming alternative to the SQL
functions (`logicaldecoding-sql.md`). **This §49.3 page is itself a short
pointer**; it establishes that logical-slot control + change streaming is
*exclusively* a replication-protocol affair, then defers wire detail to §54.4
(`protocol-replication.md`).

## What the page actually states

- Logical decoding can be controlled and consumed **over the streaming
  replication protocol** (the walsender), not only via SQL. [from-docs]
- The relevant commands are issued on a **replication connection**:
  `CREATE_REPLICATION_SLOT slot LOGICAL output_plugin`,
  `START_REPLICATION SLOT slot LOGICAL ...`, and `DROP_REPLICATION_SLOT slot
  [WAIT]`. **These commands are available *only* over a replication connection —
  they cannot be used via SQL.** [from-docs]
- `pg_recvlogical` is a client wrapper that **uses these commands internally.**
  [from-docs]
- Full wire-level mechanics (option passing to the plugin, keepalives, standby
  status / feedback messages, connection setup) live in §54.4 Streaming
  Replication Protocol, not here. [from-docs] → `protocol-replication.md`.

## Why it matters (cross-page)

- **Only the walsender path supports synchronous replication** — the SQL
  function interface does not (stated in §49.4, see `logicaldecoding-sql.md`).
  So a synchronous logical consumer must use this streaming interface.
- The replication connection that carries these is a **`replication=database`**
  connection (a logical-decoding walsender is attached to a specific database,
  unlike a physical walsender). [inferred — confirm against protocol-replication]

## Links into corpus

- [[knowledge/docs-distilled/logicaldecoding-sql.md]] — the SQL-function
  alternative (no synchronous-replication support).
- [[knowledge/docs-distilled/protocol-replication.md]] — §54.4, the wire-level
  spec these commands defer to.
- [[knowledge/idioms/walsender-state-machine.md]] — the walsender loop that
  serves START_REPLICATION ... LOGICAL.
- [[knowledge/idioms/output-plugin-callbacks.md]] — what the plugin emits down
  this stream.
- [[knowledge/subsystems/replication.md]] — slot + walsender subsystem.

## Open questions

- Verify the exact set of replication-protocol commands and the
  `replication=database` requirement against `protocol-replication.md` / the
  walsender grammar at anchor `bdae2c20e88d`.
