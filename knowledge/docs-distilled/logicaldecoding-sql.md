---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-sql.html
fetched_at: 2026-06-19T18:50:00Z
anchor_sha: bdae2c20e88d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
also_fetched:
  - https://www.postgresql.org/docs/current/functions-admin.html  # §9.28.6 Replication Management Functions — where the actual signatures/semantics live
---

# Logical Decoding SQL Interface (logical-decoding ch. 49.4)

The SQL-function path to logical decoding — the alternative to the walsender
streaming interface (`logicaldecoding-walsender.md`). **The §49.4 page itself is
a stub** that defers signatures to §9.28.6 (Replication Management Functions)
and makes exactly one substantive claim; the function semantics below are
salvaged from `functions-admin.html` (same leaf-page workaround documented for
`planner-stats-details` / `spi-transaction`).

## The one §49.4 claim

- **Synchronous replication is only supported on slots used over the streaming
  replication interface.** The SQL function interface (and other non-core
  interfaces) do **not** support synchronous replication. [from-docs]

## The functions (signatures from §9.28.6)

- `pg_create_logical_replication_slot(slot_name name, plugin name [, temporary
  boolean] [, twophase boolean] [, failover boolean]) → (slot_name, lsn)` —
  creates a logical slot bound to an output plugin. `temporary` (default false) =
  session-local; `twophase` enables prepared-transaction decoding; `failover`
  syncs the slot to standbys. [from-docs]
- `pg_logical_slot_get_changes(slot_name, upto_lsn, upto_nchanges, VARIADIC
  options text[]) → setof (lsn pg_lsn, xid xid, data text)` — **consumes**.
  [from-docs]
- `pg_logical_slot_peek_changes(...)` → same columns — **non-destructive**.
  [from-docs]
- `pg_logical_slot_get_binary_changes(...)` / `pg_logical_slot_peek_binary_changes(...)`
  → same but `data bytea` (for plugins emitting binary output). [from-docs]
- `pg_replication_slot_advance(slot_name, upto_lsn) → (slot_name, end_lsn)` —
  manually fast-forwards the slot. [from-docs]
- `pg_copy_logical_replication_slot(src, dst [, temporary] [, plugin])` — copies
  a slot starting at the source's LSN; **`failover` is NOT copied** (defaults
  false). [from-docs]
- `pg_drop_replication_slot(slot_name) → void`. [from-docs]

## Get vs. peek — the crux

- **`get_*` consumes:** advances the slot's `confirmed_flush_lsn`, persisted at
  the **next checkpoint**. It is *non-destructive on error* (a failed call does
  not lose position). [from-docs]
- **`peek_*` does not consume:** `confirmed_flush_lsn` is untouched, so the
  *same* changes are returned on the next call. [from-docs]
- This `confirmed_flush_lsn`/`restart_lsn` advance is exactly what releases
  retained WAL — an unconsumed slot pins WAL back to `restart_lsn`.

## Stop conditions

- `upto_lsn` (NULL = no limit): include only transactions **committing before**
  this LSN. [from-docs]
- `upto_nchanges` (NULL = no limit): stop once produced rows exceed the value —
  but **the limit is checked only after each transaction commit, so more rows
  than `upto_nchanges` may be returned.** [from-docs]
- Both NULL → decode to end of WAL. [from-docs]

## Ordering & failover

- Changes are returned **only for committed transactions, in commit order**
  (never for in-flight/aborted xacts via the normal path). [from-docs]
- `pg_replication_slot_advance` cannot move backwards or beyond the insert
  point; returns the actual `end_lsn`; position written at next checkpoint, so a
  crash can revert it to an earlier point. [from-docs]
- For a **failover** slot, the get/peek call **does not return until** all
  physical slots in `synchronized_standby_slots` confirm WAL receipt. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/logicaldecoding-walsender.md]] — the streaming
  alternative (the only path that supports synchronous replication).
- [[knowledge/docs-distilled/logicaldecoding-example.md]] — worked get/peek/drop
  lifecycle with test_decoding.
- [[knowledge/idioms/replication-slot-advance.md]] — the C side of
  `pg_replication_slot_advance` / confirmed_flush bookkeeping.
- [[knowledge/idioms/logical-decoding-snapshot.md]] — the historic snapshot that
  makes "committed, in commit order" decoding possible.
- [[knowledge/idioms/output-plugin-callbacks.md]] — what shapes the `data`
  column.
- [[knowledge/subsystems/replication.md]] — slot/WAL-retention subsystem.

## Open questions

- Confirm at anchor `bdae2c20e88d` whether `failover` and
  `synchronized_standby_slots` gating apply equally to the binary-changes
  variants (docs describe the text path).
