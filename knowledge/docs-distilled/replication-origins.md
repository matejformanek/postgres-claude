---
source_url: https://www.postgresql.org/docs/current/replication-origins.html
fetched_at: 2026-06-13T19:52:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Replication Progress Tracking / Origins (internals ch. 50)

Replication origins solve two problems for any logical-replication apply process:
crash-safe progress tracking and loop prevention in multi-node topologies. The
output-plugin `filter_by_origin_cb` is the consumer of this metadata.

## Non-obvious claims

- **An origin has a name and an ID.** The **name** is free-form text shared across
  systems (prefix it to avoid clashes between different replication solutions); the
  **ID** is a compact internal numeric handle, **never shared across systems**
  (used for space efficiency in WAL/commit records). [from-docs]
- **Problem 1 — crash-safe progress without bloat.** Naively tracking apply
  progress by updating a row per applied transaction causes runtime overhead and
  table bloat. Origins persist the apply LSN cheaply and crash-safely instead. [from-docs]
- **Problem 2 — loop prevention.** In cyclic/bidirectional topologies, replayed
  rows would be re-replicated forever. Tagging changes with their origin lets a
  consumer filter out changes that originated from itself. [from-docs]
- **🔑 Atomic progress commit.** When the apply side configures the source txn's
  LSN/timestamp (`pg_replication_origin_xact_setup()`), the recorded replication
  progress is **persisted atomically with the replayed transaction's commit** — no
  separate write, no window where progress and data disagree after a crash. [from-docs]
- **Catalog & view:** `pg_replication_origin` stores defined origins; replay
  progress for all origins is visible in the **`pg_replication_origin_status`**
  view. [from-docs]
- **SQL surface:** `pg_replication_origin_create()` / `..._drop()`;
  `pg_replication_origin_session_setup()` marks a session as replaying from a
  remote node; `pg_replication_origin_xact_setup()` sets per-txn source LSN +
  commit timestamp; `pg_replication_origin_progress()` and
  `..._session_progress()` read back progress. [from-docs]
- **Filter hook:** the output-plugin `filter_by_origin_cb` consumes origin info to
  drop changes by source — more efficient than per-change inspection, though less
  flexible. [from-docs]

## Links into corpus

- Per-file: [[knowledge/files/src/backend/replication/logical/origin.c.md]]
  (the C API: `replorigin_create`, `replorigin_session_setup`,
  `replorigin_advance`, `replorigin_session_advance`, and the
  `pg_replication_origin` catalog access — the SQL functions above are thin
  wrappers over these). [unverified — C names not line-pinned this run]
- Subsystem: [[knowledge/subsystems/replication.md]].
- Siblings: `knowledge/docs-distilled/logicaldecoding-output-plugin.md`
  (`filter_by_origin_cb` is where origins are consumed),
  `knowledge/docs-distilled/protocol-logical-replication.md`.
