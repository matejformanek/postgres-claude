---
source_url: https://www.postgresql.org/docs/current/logical-replication-restrictions.html
fetched_at: 2026-06-30T20:01:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — Restrictions (§x.6)

The "what it does NOT do" leaf. This is where the intro's deferred questions (DDL,
sequences, TRUNCATE/FK, what object kinds replicate) are actually answered.

## What is NOT replicated

- **DDL is not replicated.** Schema must be kept in sync manually; the initial
  schema can be bootstrapped with `pg_dump --schema-only`. [from-docs]
- **Sequence data is not replicated.** Only the *data* in serial/identity columns
  replicates, **not the sequence's next-value state** — sequences sit at their
  **start value** on the subscriber (a hard failover gotcha: after promoting a
  subscriber, sequences are not advanced). [from-docs]
- **Large objects are not replicated** — no workaround; store the data in normal
  tables instead. [from-docs]

## What object kinds CAN replicate

- **Only base tables and partitioned tables.** **Views, materialized views, and
  foreign tables cannot** be replicated and **error** if you try to add them.
  [from-docs]
- **Partitioned tables replicate from leaf partitions by default** — the leaves
  must exist as valid targets on the subscriber (they may be further
  sub-partitioned or be independent tables there). `publish_via_partition_root`
  switches to replicating via the **root** table's identity instead. [from-docs]

## TRUNCATE + foreign keys

- TRUNCATE replication truncates the **same table group** on the subscriber, but
  **fails if a truncated table has a foreign-key link to a table outside the
  subscription**. [from-docs] (FK closure must be inside the replicated set.)

## REPLICA IDENTITY FULL datatype limit

- With **`REPLICA IDENTITY FULL`**, `UPDATE`/`DELETE` **cannot apply on the
  subscriber if a table has datatypes without a B-tree or Hash operator class**
  (e.g. `point`, `box`) — unless a primary key / narrower replica identity is
  defined. [from-docs] (FULL builds the row-match predicate from every column, so
  every column type needs an equality/ordering opclass.)

## Live schema changes

- Schemas need not be identical, but a **live schema change on the publisher can
  cause replication errors** until the subscriber's schema is updated. Doing
  **additive changes on the subscriber first** avoids the intermittent-error
  window. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/logical-replication.md` — the intro that defers here.
- `knowledge/docs-distilled/logical-replication-publication.md`,
  `logical-replication-failover.md` — replica-identity + sequence-state
  implications.
- `knowledge/docs-distilled/logical-replication-col-lists.md` — partitioned-table
  `publish_via_partition_root` behaviour.
- `knowledge/subsystems/replication.md` — decode-side object-kind gating.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-restrictions.html
  (PG18). The sequence-state and REPLICA IDENTITY FULL opclass restrictions are
  the most plan-relevant; verify against
  `source/src/backend/replication/logical/` at anchor `b7e4e3e7fa73`.
