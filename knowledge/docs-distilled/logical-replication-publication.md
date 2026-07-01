---
source_url: https://www.postgresql.org/docs/current/logical-replication-publication.html
fetched_at: 2026-06-30T19:56:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — Publication (§x.1)

The publisher-side object. A **publication** is a named change-set (a.k.a.
"replication set") generated from one or more tables; subscriptions on other nodes
attach to it.

## What a publication is

- A publication is a **set of changes generated from a table or group of tables**
  — also called a *change set* or *replication set*. [from-docs]
- **Each publication lives in exactly one database.** [from-docs]
- Publications are defined on a **physical replication primary** (the publisher);
  you cannot publish from a physical standby. [from-docs]
- A publication is **not a schema** and does **not** affect how the underlying
  tables are accessed by ordinary queries. [from-docs]

## Membership

- A table may belong to **multiple publications** simultaneously. [from-docs]
- Publications may currently contain **only tables and "all tables in schema"**
  targets — not arbitrary object kinds. [from-docs]
- Objects are added **explicitly**, except for a `FOR ALL TABLES` publication which
  auto-includes every current and future table. [from-docs]
- Membership is editable with `ALTER PUBLICATION ... ADD/DROP TABLE`, and both
  ADD and DROP are **transactional**. [from-docs]
- A publication can have **multiple subscribers**. [from-docs]

## The `publish` parameter (which DML is replicated)

- `publish` limits replicated changes to any combination of `INSERT`, `UPDATE`,
  `DELETE`, `TRUNCATE`. **Default: all four are replicated.** [from-docs]
- These settings apply **only to DML in steady state** — they do **not** affect
  the **initial data synchronization** (the COPY snapshots the table regardless of
  `publish`). [from-docs] (Same point the `-architecture` leaf makes from the
  subscriber side.)
- **Row filters have no effect on `TRUNCATE`.** [from-docs]

## Replica identity — the UPDATE/DELETE gate

This is the most error-prone part of setting up a publication:

- A published table must have a **replica identity** configured to replicate
  `UPDATE`/`DELETE`. **Default replica identity = the primary key** (when one
  exists). [from-docs]
- Alternatives: a **unique index** (with extra requirements), or replica identity
  **`FULL`** (the entire row becomes the key). [from-docs]
- Tables with replica identity **`NOTHING`**, **`DEFAULT` but no primary key**, or
  **`USING INDEX` with a since-dropped index** **cannot UPDATE/DELETE** when in a
  publication that replicates those actions — the operation **errors on the
  publisher**. [from-docs] (Failure surfaces at write time on the *publisher*, not
  at apply time — a common debugging surprise.)
- **`INSERT` proceeds regardless of replica identity.** [from-docs]
- If a non-`FULL` replica identity is set on the publisher, the subscriber must
  have the **same or fewer** identity columns. [from-docs]

## What this leaf does NOT cover (other leaves / reference)

- `publish_via_partition_root`, partition-publication semantics, and the exact
  privileges to `CREATE PUBLICATION` are in the **`CREATE PUBLICATION` reference
  page**, not in this overview leaf. [unverified — not on this page; flagged so a
  plan doesn't cite this slug for them]
- Row-filter and column-list *evaluation* are the `-row-filter` / `-col-lists`
  leaves.

## Links into corpus

- `knowledge/docs-distilled/logical-replication-subscription.md` — the consuming
  side.
- `knowledge/docs-distilled/logical-replication-row-filter.md`,
  `logical-replication-col-lists.md` — per-table filtering this leaf references.
- `knowledge/docs-distilled/logical-replication-architecture.md` — `pgoutput`
  filters per the publication spec.
- `knowledge/subsystems/replication.md` — `pg_publication` catalog + decode path.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-publication.html
  (PG18). `publish_via_partition_root` / partition / privilege items are flagged
  as NOT on this page — verify against the `CREATE PUBLICATION` reference +
  `source/src/backend/catalog/pg_publication.c` at anchor `b7e4e3e7fa73`.
