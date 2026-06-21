---
source_url: https://www.postgresql.org/docs/current/logical-replication-architecture.html
fetched_at: 2026-06-20T19:55:00Z
anchor_sha: dc5116780846
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication Architecture (§31.10 family — Architecture / Initial Snapshot)

The "how built-in pub/sub actually runs" leaf of the §31 Logical Replication
chapter. **Distinct from the already-distilled §49 logical-*decoding* family**:
§49 is the low-level decoding plugin API (`pgoutput` and friends); this page is
the **subscriber-side process model** — the walsender + apply worker + tablesync
workers that move data into local tables.

## The two core processes

- **`walsender` (publisher side):** starts logical decoding of the WAL and loads
  the standard output plugin **`pgoutput`**, which transforms WAL changes into
  the logical replication protocol (§54.5 wire format) and **filters** per the
  publication spec (tables, row filters, column lists). [from-docs]
- **`apply` worker (subscriber side):** maps incoming changes to local tables and
  applies them individually **in correct transactional / commit order**. [from-docs]
- The apply worker runs with `session_replication_role = replica`, so by default
  **triggers and rules do NOT fire**; they fire only if the table's triggers/rules
  are explicitly enabled for replica via `ALTER TABLE ... ENABLE TRIGGER` /
  `ENABLE RULE`. The apply path fires **row** triggers only, never statement
  triggers. [from-docs]

## Initial table synchronization (§31.10.1)

- Initial data in subscribed tables is copied by dedicated **table
  synchronization (tablesync) workers** — special apply processes. [from-docs]
- **Each table to be synced gets its own tablesync worker**, and **each worker
  creates its own replication slot** and copies the existing data. [from-docs]
- After the bulk copy, the worker enters **synchronization mode**: changes that
  happened *during* the copy are streamed via normal logical replication and
  applied/committed in **publisher order**; once caught up, control hands back to
  the main apply worker. This is the COPY-then-catch-up handshake that lets a
  table go live without losing concurrent writes. [from-docs]
- The COPY-based initial sync fires **both** row and statement triggers for the
  synthetic `INSERT`s (unlike the steady-state apply path, which is row-only).
  [from-docs]
- A publication's `publish` parameter affects **only which DML is replicated** in
  steady state — it does **not** affect initial data synchronization (the COPY
  snapshots the table regardless). [from-docs]
- Failed tablesync workers are **respawned by the apply worker**, so transient
  errors don't permanently stall replication; retry cadence relates to
  `wal_retrieve_retry_interval`. [from-docs]

## What this leaf does NOT spell out (read elsewhere)

- The **logical replication launcher** background worker and the
  `max_logical_replication_workers` / `max_sync_workers_per_subscription` GUCs
  that bound concurrent apply/tablesync workers are described in the surrounding
  §31 / config chapters, **not** in this architecture leaf. [unverified — not on
  this page]
- **Replication origins** (the `pg_replication_origin` mechanism that records how
  far the subscriber has applied, for crash-safe resume) underpin apply progress
  tracking but aren't named on this page — see the §49 / replication-origins
  corpus. [inferred]
- Row-filter / column-list *evaluation* semantics live in their own §31 leaves;
  here they appear only as "the output plugin filters per publication spec".

## Links into corpus

- `knowledge/docs-distilled/logicaldecoding-explanation.md`,
  `knowledge/docs-distilled/logicaldecoding-output-plugin.md` — the §49
  decoding/`pgoutput` layer the walsender drives.
- `knowledge/docs-distilled/protocol-logical-replication.md`,
  `knowledge/docs-distilled/protocol-logicalrep-message-formats.md` — the §54.5
  wire format `pgoutput` emits.
- `knowledge/docs-distilled/replication-origins.md` — apply-progress tracking.
- `knowledge/idioms/apply-worker-loop-and-dispatch.md`,
  `knowledge/idioms/apply-handlers-insert-update-delete.md`,
  `knowledge/idioms/apply-streaming-and-parallel.md` — the apply-worker internals.
- `knowledge/idioms/tablesync-initial-copy.md` — the COPY-then-catch-up handshake
  in code.
- `knowledge/idioms/walsender-state-machine.md`,
  `knowledge/idioms/replication-origin-tracking.md`,
  `knowledge/subsystems/replication.md` — publisher side + subsystem map.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-architecture.html
  (PG18). GUC names for worker limits and the launcher process are explicitly
  flagged as NOT on this page; verify against runtime-config-replication +
  `source/src/backend/replication/logical/` at anchor `dc5116780846` before
  asserting them in a plan.
