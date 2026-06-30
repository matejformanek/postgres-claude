---
source_url: https://www.postgresql.org/docs/current/logical-replication-row-filter.html
fetched_at: 2026-06-30T19:59:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — Row Filters (§x.3)

Per-table `WHERE` clause on a publication that restricts *which rows* replicate.
The subtle parts are the **UPDATE-transformation** behaviour and the
**OR-combining** rule across publications.

## Syntax + expression restrictions

- A row filter is a **parenthesised `WHERE`** clause after the table name in
  `CREATE PUBLICATION ... FOR TABLE t WHERE (...)`. [from-docs]
- The expression must be **simple**: **no** user-defined functions, operators,
  types, collations; **no** system-column references; **no** non-immutable
  built-in functions. [from-docs]
- The `WHERE` expression is **evaluated using the role named in the subscription's
  `CONNECTION` clause** — not the publication owner. [from-docs]

## Replica-identity constraint (the UPDATE/DELETE gate)

- If the publication publishes **`UPDATE`/`DELETE`**, the filter may reference
  **only columns covered by the table's `REPLICA IDENTITY`**. For
  **`INSERT`-only** publications, **any** column may be used. [from-docs] (Same
  replica-identity theme as the publication + col-list leaves.)

## Evaluation semantics

- The filter is applied **before** publishing; if it evaluates **`false` or
  `NULL`**, the row is **not** replicated. [from-docs] (NULL ⇒ not replicated —
  a three-valued-logic trap.)
- **UPDATE transformation** — the filter runs against **both old and new row**:
  - both true → replicate as `UPDATE`;
  - both false → not replicated;
  - **old true, new false → `UPDATE` becomes a `DELETE`** (row leaves the set);
  - **old false, new true → `UPDATE` becomes an `INSERT`** (row enters the set).
  [from-docs] This row-move rewriting is the non-obvious core of row filters.
- **`TRUNCATE` ignores row filters.** [from-docs]

## Combining across publications

- Same table in **multiple publications** with different filters → the filters are
  **OR-ed** (a row replicates if it satisfies **any**). [from-docs]
- If **any** of those publications has **no filter**, or is `FOR ALL TABLES` /
  `FOR TABLES IN SCHEMA`, **all other filters become redundant** (no filtering for
  that table). [from-docs]

## Initial sync + partitions

- **Initial COPY respects row filters** (only matching rows copy) — note this is
  the **one place** the `-publication`/`-subscription` leaves' "COPY ignores
  filters" claim is *refined*: COPY ignores the `publish` op-list but **does**
  honour row filters; with multiple publications, rows matching **any** filter
  copy. [from-docs] (Cross-check: the subscription leaf phrased COPY as ignoring
  filters — the precise rule per this leaf is that the row filter IS applied at
  initial sync.)
- **Partitioned tables:** `publish_via_partition_root` decides whether the **root
  table's** filter or **each partition's** filter applies. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/logical-replication-publication.md` — `publish`,
  replica identity.
- `knowledge/docs-distilled/logical-replication-col-lists.md` — the column-level
  twin of this row-level filter.
- `knowledge/docs-distilled/logical-replication-architecture.md` — `pgoutput`
  applies the filter.
- `knowledge/subsystems/replication.md` — filter evaluation in the decode path.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-row-filter.html
  (PG18). The UPDATE→INSERT/DELETE transformation and the COPY-honours-row-filter
  point are the most plan-relevant; verify against
  `source/src/backend/replication/pgoutput/pgoutput.c` at anchor `b7e4e3e7fa73`.
