---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-synchronous.html
fetched_at: 2026-06-13T19:51:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Synchronous Replication Support for Logical Decoding (internals ch. 49.8)

Logical decoding rides the *same* streaming-replication protocol as physical
standbys, so it can be made synchronous — with one sharp scoping caveat and a
small family of catalog-lock deadlock traps. Companion to
`protocol-replication.md` / `runtime-config-replication.md`.

## Non-obvious claims

- **Reuses the physical replication interface:** a logical decoding client streams
  over the same protocol (ch. 47.3 / §54.4) and must send **`Standby status
  update (F)`** feedback messages exactly like a physical streaming client. That
  feedback is what lets the primary count it toward synchronous durability. [from-docs]
- **🔑 Single-database scoping incompatibility.** Synchronous logical replication
  hangs on **`synchronous_standby_names`, which is server-wide**, while a logical
  receiver only covers **one database**. So if more than one database is actively
  written, the technique **does not work properly** — the server-wide sync set
  can't be satisfied by a per-database consumer. [from-docs] This is the headline
  gotcha, not a footnote.
- **Durability/latency is the usual sync tradeoff:** commits block until the
  logical consumer's flush feedback arrives; there's no logical-specific knob
  beyond the standard `synchronous_commit` / `synchronous_standby_names`. [inferred
  from docs]
- **Catalog-lock deadlock traps** (because decoding itself takes catalog locks to
  interpret tuples). Avoid, inside a transaction that's being decoded synchronously:
  explicit `LOCK pg_class`; `CLUSTER` on `pg_class`; `PREPARE TRANSACTION` after a
  `LOCK pg_class` (with 2PC decoding on); `PREPARE TRANSACTION` after `CLUSTER
  pg_trigger` when the published table has triggers (2PC on); `TRUNCATE` of a
  user-catalog table. The list is illustrative — other catalog tables can deadlock
  too. [from-docs]

## Links into corpus

- Per-file: [[knowledge/files/src/backend/replication/syncrep.c.md]]
  (synchronous-commit wait machinery driven by `synchronous_standby_names`),
  [[knowledge/files/src/backend/replication/walsender.c.md]]
  (the sender that processes `Standby status update` feedback),
  [[knowledge/files/src/backend/replication/logical/logical.c.md]].
- Subsystem: [[knowledge/subsystems/replication.md]].
- Siblings: `knowledge/docs-distilled/protocol-replication.md`,
  `knowledge/docs-distilled/runtime-config-replication.md`,
  `knowledge/docs-distilled/logicaldecoding-explanation.md`.
